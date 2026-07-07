# Module-Based Access Control — Plan (for review)

Supersedes the *configuration* model in `ACCESS_CONTROL_PLAN.md` (per-resource `enforced`
flag + per-resource grants). The app-side wiring from that plan (the `mobile.ui.resource`
catalog, the `canView`/`canDo`/`PermissionGate` layer, the `{enforced, granted}` payload)
is **kept and reused** — only how the backend *computes* access changes.

Status: **proposal — not yet built.** Nothing here is applied until approved.

---

## 1. Goal

Give each role access by **module**, not by hand-picking dozens of screens. Four core
modules: **Primary Sales, Secondary Sales, HR, Expense**. Assigning a module grants
everything in it; two per-group **exception lists** subtract specific screens/buttons.

```
visible-to-role = (resources of the role's assigned modules) − (hidden menus + hidden buttons)
```

**Decisions locked:** resource↔module is **m2m**; the old `enforced` flag + per-resource
grant list are **dropped**.

---

## 2. Why the app does NOT change

The app only ever consumes `{enforced, granted}` and computes
`visible(key) = key ∉ enforced OR key ∈ granted`. The module model just fills those two
lists differently, server-side:

```
enforced = every resource attached to ANY module      # "module-managed"
granted  = (assigned modules' resources) − (hidden menus ∪ hidden buttons)
```

Result per key:
| situation | in enforced? | in granted? | app shows? |
|---|:--:|:--:|:--:|
| in an assigned module, not hidden | yes | yes | **shown** |
| in an assigned module, hidden | yes | no | hidden |
| in a module the role lacks | yes | no | hidden |
| attached to **no** module (new/unclassified) | no | — | **shown** (safe default) |

→ **No Flutter change, no rebuild.** `canView`/`canDo`/`PermissionGate` stay byte-identical.

---

## 3. Backend data model

**New — `ss.module`**
```
name        Char
code        Char (unique)
sequence    Integer
resource_ids  m2m → mobile.ui.resource     # what this module contains
active      Boolean
```

**Change — `mobile.ui.resource`**
- remove: `enforced` (bool), `group_ids` (old grant m2m)
- add: `module_ids  m2m → ss.module` (mirror of `ss.module.resource_ids`)
- keep: `key, res_type, module, label, active, last_seen`

**Change — `res.mobile.user.group`**
- remove: `ui_resource_ids` (old allowlist)
- add:
  ```
  module_ids         m2m → ss.module                        # role's modules
  hidden_menu_ids    m2m → mobile.ui.resource (res_type=screen)   # exception list
  hidden_button_ids  m2m → mobile.ui.resource (res_type=action)   # exception list
  ```
- keep: `can_manage_access`; and the legacy flags (`can_view_all_returns`,
  `can_edit_*`, `skip_attendance_geolocation`) stay for the login `permissions`
  block’s fallback — unused once those actions are module-managed.

**Rewrite — `MobilePolicy` / payload builder**
```python
# mobile.ui.resource
def get_access_payload(self, group=None):
    Resource = self.env['mobile.ui.resource'].sudo()
    enforced = Resource.search([('module_ids', '!=', False), ('active', '=', True)]).mapped('key')
    granted = []
    if group:
        module_res = group.sudo().module_ids.mapped('resource_ids').filtered('active')
        hidden = group.sudo().hidden_menu_ids | group.sudo().hidden_button_ids
        granted = (module_res - hidden).mapped('key')
    return {'enforced': enforced, 'granted': granted}

# MobilePolicy.has_ui_access(key): allow if key not module-managed, else key in granted-set
```

**Views**
- `ss.module` form: name/code + its `resource_ids` (filterable by type).
- Group form: replace the "UI Access" tab with **Modules** + **Hidden Menus** +
  **Hidden Buttons**.
- `mobile.ui.resource` form: show `module_ids`; drop the `enforced` toggle.
- Menu: keep **UI Access Catalog**; add **Modules** under Configuration.

**Security**: `ir.model.access` rows for `ss.module` (+ its m2m); reuse the two mobile
groups (user read / manager RW).

---

## 4. How screens & actions get INTO Odoo (your sync question)

Nothing is typed by hand. The **app is the source of truth** for the list:

1. All keys live in one Dart file — `lib/core/access/access_resources.dart` → the
   `accessCatalog` const (currently 64: 43 screens + 21 actions).
2. **Settings → “Sync Access Catalog”** (as a user whose mobile group has
   `can_manage_access`) POSTs the whole list to `POST /api/v1/access/catalog/sync`.
3. Odoo **upserts** every entry into `mobile.ui.resource` (adds new keys, updates
   labels, archives keys the app dropped). One tap = the entire catalog.
4. You then drag resources into modules (Section 5) — a one-time setup, editable anytime.

Re-run the sync after any app release that adds/removes keys. There is **no Odoo-side
auto-discovery** — Odoo can’t see Flutter widgets; the app tells it.

> **“All screens and all actions” caveat:** the catalog is only as complete as
> `accessCatalog`. It covers every surface we’ve wired so far, not literally every widget.
> Making it exhaustive = enumerating each screen + gateable button in that one Dart file
> (mechanical, no auto-gen). We extend it incrementally as we wrap more surfaces.

---

## 5. Proposed module ↔ resource seeding (adjust freely in the UI after)

`PS` = Primary Sales · `SS` = Secondary Sales · `HR` · `EX` · `—` = unattached (visible to all)

**Primary Sales (PS)**
- Screens: module.primary, contacts.dealers, contacts.distributor_detail,
  contacts.create_distributor, sales.primary_list, sales.create_primary,
  sales.order_detail, sales.deliveries_list*, returns.list, returns.create,
  scraps.list*, scraps.create*
- Actions: returns.view_all, returns.edit_so_qty, returns.edit_qc_qty,
  returns.edit_effective_qty, returns.create, scraps.create*, sales.order_confirm,
  sales.order_cancel, sales.delivery_validate*, contacts.distributor_create

**Secondary Sales (SS)**
- Screens: module.secondary, sales.secondary_orders_list, sales.order_create,
  sales.product_selection, sales.validate_delivery, sales.deliveries_list*,
  contacts.outlets_list, contacts.edit_outlet, routes.* (list/detail/create/
  create_outlet/visits_list/new_joint_visit), van_loading.* (list/form/location_detail),
  transfers.* (list/detail/create/create_location), scraps.list*, scraps.create*
- Actions: sales.order_create, sales.order_confirm, sales.order_cancel,
  sales.delivery_validate*, transfers.create/validate/cancel, routes.create,
  routes.add_outlet, contacts.outlet_create, scraps.create*, visits.check_in,
  visits.check_out

**HR** — Screens: module.attendance, module.leave, hr.attendance, hr.leave · Actions: hr.skip_attendance_geo
**Expense (EX)** — Screens: module.expense, hr.expense
**Unattached (—, visible to all)** — dashboard, settings
**Employees (management)** — employees.list/detail/create + action.employees.create → PS **and** SS

`*` = shared resource, sits in **both** PS and SS via m2m.

---

## 6. Re-migrate `ss_test` to reproduce today’s scenario, module-style

1. Create the 4 modules + seed §5 mapping.
2. Every group: `module_ids = [PS, SS, HR, EX]` (baseline = full access).
3. Per-role exceptions:
   | group | hidden menus | hidden buttons |
   |---|---|---|
   | **so** | sales.primary_list, contacts.dealers, sales.deliveries_list | — |
   | **lc** | sales.primary_list, contacts.dealers, sales.deliveries_list | returns.create, scraps.create |
   | **tsm** | — | — |
   | **soo** | — | returns.create |
4. Clear the old per-resource grants + `enforced` flags (ignored after the rewrite).

Reproduces exactly: SO/LC see only Return Delivery + Return Scrap in Primary; LC has no
create buttons; TSM full; SO keeps Secondary in full (those keys are only *code-gated* on
the Primary cards).

---

## 7. Build order & verification

1. `ss.module` model + fields on resource/group + security. `compileall` + XML parse.
2. Rewrite payload/`has_ui_access`. 3. Views. 4. Upgrade `-u meta_api_user,meta_ss_rest_api`.
5. App: **Sync Access Catalog** (populates resources). 6. Create modules + seed mapping.
7. Set group modules + hide-lists (§6). 8. Log in per role in the app and verify.

App: **no rebuild** (the `{enforced, granted}` contract is unchanged).

---

## 8. What gets removed

- `mobile.ui.resource.enforced`, `mobile.ui.resource.group_ids`
- `res.mobile.user.group.ui_resource_ids`
- The enforced-toggle + grant UI on the group form.

Kept: the catalog, the sync endpoints, `/access/permissions`, the app wiring, the login
`access` block, the legacy `permissions` flags (fallback only).

---

## 9. Trade-off to accept

Grant-module-then-hide is a **denylist within a module**: a *new* screen later added to a
module is auto-granted to every role holding that module unless hidden. For
role-owns-module thinking this is the desired default — noted so it’s a conscious choice.

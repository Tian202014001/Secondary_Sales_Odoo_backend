# Server-Side Access Enforcement — Full Design Document

**Status:** design, for review. Code later.
**Extends:** `API_ENDPOINT_SOP.md`, `AUTHORIZATION_IMPLEMENTATION.md`.
**App counterpart:** `secondary_sales/ACCESS_AUDIT.md`, `MODULE_ACCESS_PLAN.md`.

---

## 1. Purpose

The mobile app already **hides** screens/buttons based on the module access config
(`{enforced, granted}` in the login payload). But hiding a button is UX, not security — a
modified or replayed client can still call the business endpoints directly. This document
specifies how the backend **enforces** the same access config at the API, so an
unauthorized capability is refused server-side regardless of what the client sends.

Goal in one line: **make the module/UI access config the real access boundary, applied
identically on the app and the server, from one source of truth.**

Scope: the *UI-action/capability* layer (create order, validate transfer, edit QC qty, …).
This is **orthogonal to** and **layered on top of** the existing data-authorization
(`ir.model.access` + record rules), which already governs *which rows* a group may
read/write.

---

## 2. Current state

### Already in place (reuse)
- **Token-derived identity.** `get_mobile_api_context(payload)` validates the bearer JWT
  and returns the trusted `mobile_user`, overriding any client-supplied `employee_id`.
  "Who is calling" is already trustworthy on any SOP-compliant endpoint.
- **`MobilePolicy.has_ui_access(key)`** (`meta_ss_rest_api/utils/mobile_policy.py`) — the
  per-key allow/deny primitive.
- **`mobile.ui.resource.get_access_payload(group)`** — builds the `{enforced, granted}`
  block the app consumes.
- **Data-layer authz** for some endpoints: `check_mobile_model_access`,
  `apply_mobile_rule_domain`.

### The two gaps
1. **Business endpoints don't call `has_ui_access`.** Nothing checks the capability the
   endpoint performs.
2. **`has_ui_access` and `get_access_payload` are separate implementations** of the same
   modules−hides logic → they can drift, so the app UI and the server could disagree.

---

## 3. Design principles

1. **Single source of truth.** The app payload and the server checks derive from **one**
   resolver, so UI visibility and API enforcement provably match (§4).
2. **The rule is `enforced` + `granted`, not `granted` alone.** A key not attached to any
   module is *allowed for everyone* (safe default). Checking only "key ∈ granted" would be
   stricter than the app and cause mismatches (§4.1).
3. **Safe-by-default rollout.** Because unmanaged keys allow everyone, checks can be added
   incrementally with zero risk; each key "turns on" only once an admin puts it in a
   module — same behavior as the app.
4. **sudo-proof.** Checks read the mobile group explicitly, never `env.is_admin()`, so
   `.sudo()` does not bypass them (SOP §5).
5. **Key consistency.** The server enforces with the **same keys the app gates with**
   (§7).

---

## 4. Core implementation

### 4.1 The rule

```
allow(key) =  key is NOT module-managed        # "not in enforced" — safe default
           OR key ∈ group's effective grants   # "in granted"      — modules − hides
```

- **module-managed** = the resource is attached to ≥1 module (and active).
- **effective grants** = resources of the group's assigned modules, minus its
  `hidden_menu_ids` / `hidden_button_ids`.

Checking only the second clause (`key ∈ granted`) would deny every unmanaged key
(default-deny) while the app allows it (default-allow) → divergence. Both clauses are
mandatory.

### 4.2 One resolver, two primitives (kills the drift)

Define the effective set **once** and have both the app payload and the server check use
it. Put the shared primitives on `mobile.ui.resource`:

```python
class MobileUiResource(models.Model):
    _inherit = "mobile.ui.resource"   # (or in the existing definition)

    @api.model
    def _is_ui_managed(self, resource):
        """A resource is 'enforced' iff it belongs to any module and is active."""
        return bool(resource) and resource.active and bool(resource.module_ids)

    @api.model
    def _group_ui_grants(self, group):
        """Effective granted resources for a group: modules' resources − hides.
        Returns a recordset. Empty for no group."""
        if not group:
            return self.browse()
        module_res = group.sudo().module_ids.mapped("resource_ids").filtered("active")
        hidden = group.sudo().hidden_menu_ids | group.sudo().hidden_button_ids
        return module_res - hidden
```

**App payload** (unchanged output, now derived from the shared primitive):

```python
    @api.model
    def get_access_payload(self, group=None):
        enforced = self.sudo().search([("module_ids", "!=", False), ("active", "=", True)])
        granted = self._group_ui_grants(group)
        return {"enforced": enforced.mapped("key"), "granted": granted.mapped("key")}
```

**Server check** (`MobilePolicy.has_ui_access`, now the same rule):

```python
    def has_ui_access(self, key):
        if not self.mobile_user:
            return False
        Resource = self.mobile_user.env["mobile.ui.resource"].sudo()
        resource = Resource.search([("key", "=", key), ("active", "=", True)], limit=1)
        if not Resource._is_ui_managed(resource):
            return True                                   # unmanaged → allow (safe default)
        group = self.group
        if not group:
            return False
        return resource in Resource._group_ui_grants(group)
```

Now `has_ui_access(key)` and `get_access_payload` cannot disagree — both are
`_is_ui_managed` + `_group_ui_grants`. The Odoo **Effective Access** tab (the group's
`effective_resource_ids`) should also be computed from `_group_ui_grants`, making it the
single visible oracle for app UI, server enforcement, and admin review.

### 4.3 The enforcement helper

Add to `meta_ss_rest_api/utils/common.py`, mirroring `check_mobile_model_access`:

```python
def check_ui_access(mobile_user, key):
    """Raise AccessDenied unless the user's group may use UI resource `key`."""
    if not MobilePolicy(mobile_user).has_ui_access(key):
        raise AccessDenied("You do not have access to this action.")
```

### 4.4 Where to call it — endpoint pattern

Right after auth, before the write (SOP §2 template + one line):

```python
@http.route(f"{API_PREFIX}/virtual-transfers/<int:tid>/action", type="json", auth="user", methods=["POST"])
def transfer_action(self, tid, **payload):
    try:
        mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        action = payload.get("action")
        check_ui_access(mobile_user, {
            "validate": "action.transfers.validate",
            "cancel":   "action.transfers.cancel",
        }.get(action, ""))            # "" → unmanaged → allowed; unknown actions fall through to validation
        # ... existing model-access check + ORM (.sudo(), api_env) ...
    except Exception as exc:
        return handle_api_exception(exc)
```

### 4.5 Optional: a decorator (once the pattern is proven)

```python
def requires_ui_access(key):
    def deco(fn):
        @functools.wraps(fn)
        def wrap(self, *a, **kw):
            mobile_user = check_api_permission()          # token-derived
            check_ui_access(mobile_user, key)
            return fn(self, *a, **kw)
        return wrap
    return deco
```
Inline is more consistent with the current SOP; adopt the decorator only for endpoints
whose key is static (not payload-dependent like the transfer example).

---

## 5. Endpoint → key mapping (the actual work)

### 5.1 Writes — enforce first (highest value)

| Endpoint (operation) | Key |
|---|---|
| `/sale-orders/create` (sale_type = primary) | `screen.sales.create_primary` |
| `/sale-orders/create` (sale_type = secondary) | `screen.sales.order_create` |
| `/sale-orders/{id}/action` confirm / cancel | `action.sales.order_confirm` / `action.sales.order_cancel` |
| `/deliveries` validate | `action.sales.delivery_validate` |
| `/virtual-transfers/create` | `action.transfers.create` |
| `/virtual-transfers/{id}/action` validate / cancel | `action.transfers.validate` / `action.transfers.cancel` |
| `/virtual-locations/create` | `screen.transfers.create_location` |
| `/returns/create` | `action.returns.create` |
| `/scraps/create` | `action.scraps.create` |
| `/routes/create` | `action.routes.create` |
| `/routes/{id}` add-outlet / route-line create | `action.routes.add_outlet` |
| `/contacts/create` (distributor / outlet) | `action.contacts.distributor_create` / `action.contacts.outlet_create` |
| `/employees/create` | `action.employees.create` |
| `/route-visits` create (check-in) / update (check-out) | `action.visits.check_in` / `action.visits.check_out` |
| leave create / expense create | `action.hr.leave_create` / `action.hr.expense_create` |

### 5.2 Field-level (returns/scraps quantity edits)

Finer than a button: `/returns/create` & `/scraps/*` must reject writes to specific
quantity fields unless the group is granted them — check **per field** before the ORM
write, not just once at the endpoint:

| Field written | Required key |
|---|---|
| SO qty | `action.returns.edit_so_qty` |
| QC qty | `action.returns.edit_qc_qty` |
| Effective / done qty | `action.returns.edit_effective_qty` |

### 5.3 Reads — optional, defense-in-depth (lower priority)

Gate list/detail GETs by screen key so a user without the module can't read via API even
where record rules would otherwise return rows:

| Endpoint | Key |
|---|---|
| `/contacts` (distributor / outlet list) | `screen.contacts.dealers` / `screen.contacts.outlets_list` |
| `/sale-orders` (primary / secondary) | `screen.sales.primary_list` / `screen.sales.secondary_orders_list` |
| `/virtual-transfers` | `screen.transfers.list` |
| `/routes` | `screen.routes.list` |
| `/returns` , `/scraps` | `screen.returns.list` , `screen.scraps.list` |

Record rules already scope *which rows* are returned; this only adds *whether the endpoint
is usable at all*. Apply where it adds value.

---

## 6. Prerequisite (verify before enforcing)

Every endpoint being enforced must derive identity from the **token** — actually call
`get_mobile_api_context` and use the returned `mobile_user`, never a client-supplied
`employee_id` (SOP §3). Enforcement is meaningless on an endpoint that still trusts request
params. Audit each controller first; this is the same **JWT-enforcement P0** flagged in the
app repo's `FIXES.md`.

---

## 7. Key-consistency decisions

Server and app must use the **same key per capability**, or config won't line up.

- **Sale-order create:** the app gates the two create buttons by *screen* keys
  (`screen.sales.create_primary`, `screen.sales.order_create`); `action.sales.order_create`
  is currently **unused**. Decide: enforce `/sale-orders/create` by those two screen keys
  (recommended — matches the app), and drop/repurpose `action.sales.order_create`.
- **Every other capability** uses its natural `action.*` key, already wired in the app.

---

## 8. Rollout phasing

1. **Refactor to one resolver** — `_is_ui_managed` + `_group_ui_grants`; point
   `get_access_payload`, `has_ui_access`, and the group's `effective_resource_ids` at them.
   (Behavior-neutral; removes drift.)
2. Add the `check_ui_access` helper.
3. Enforce **writes**, high-value first: transfers (validate/cancel/create), sale-order
   create (by sale_type), returns/scraps create, deliveries validate.
4. Enforce **field-level** returns/scraps qty edits.
5. Enforce remaining writes: routes, contacts, employees, visits, HR.
6. (Optional) Enforce **reads** by screen key where valuable.
7. (Optional) Refactor static-key checks into `@requires_ui_access`.

The app needs **no change** — it already hides these; this makes the hiding real.

---

## 9. Testing

For each enforced endpoint, using the group's **Effective Access** tab as the oracle:

- Group **with** the key granted → succeeds.
- Group **without** it (key in an unassigned module, or in `hidden_*`) → `AccessDenied`
  → `error: "validation_error"` (or `"forbidden"`, see §10) via `handle_api_exception`.
- Key **not in any module** → allowed — confirms safe-default / incremental-rollout works.
- **Cross-check:** the keys the endpoint allows must equal the keys shown in that group's
  Effective Access tab (proves app UI ≡ server enforcement).

---

## 10. Decisions to lock

- **Reads:** enforce screen-key reads everywhere, or only sensitive lists? (Lean: only
  where it matters — record rules already scope rows.)
- **`/sale-orders/create` key:** confirm the two screen keys vs. adding
  `action.sales.*_create`. Pick one, use in both app and server (§7).
- **Error code:** keep generic `AccessDenied` → `validation_error`, or add a distinct
  `forbidden` code so the app can show "hidden by config" differently from other validation
  failures?
- **Resolver location:** put `_is_ui_managed` / `_group_ui_grants` on `mobile.ui.resource`
  (as sketched) or on `res.mobile.user.group`? (Either works; pick one home so there's a
  single canonical implementation.)

---

## 11. Summary

- Enforcement = `has_ui_access(key)` = the **full `enforced` + `granted` rule**, derived
  from **one resolver** shared with the app payload and the Effective Access tab.
- It's **one helper + one line per endpoint**, added **safely and incrementally** (unmanaged
  keys allow everyone until an admin manages them).
- The mapping table (§5) is the real work; the mechanism is trivial.
- Prerequisite: token-derived identity on every enforced endpoint (§6).

# Role-Based Access Control (RBAC) — Implementation Plan

Backend-driven, per-screen and per-action access control. The app owns a catalog of
screen/action keys and syncs it to Odoo; admins grant those keys to groups; the app
hides/disables screens and buttons a group isn't allowed to use.

**Decisions locked (2026-07-05):**
1. **Default policy = Hybrid per-resource `enforced` flag.** A resource is visible to
   everyone until an admin flips it to *enforced*; once enforced it becomes an
   allowlist (visible only to groups granted it). → migrate screen-by-screen, no
   regressions.
2. **Catalog sync = app POSTs to an Odoo endpoint** (admin/dev-triggered or on
   app-version change — never on every user launch).
3. **Enforcement = UI now, backend enforcement as a required follow-up** (folds into
   the "enforce JWT server-side" P0 in `FIXES.md`). UI gating is UX, not security.

**Standing constraint:** no existing feature may break. Phases 0–1 must reproduce
current behavior *exactly* before anything new is gated. Verify with `flutter analyze`
+ `flutter build apk --debug` after each phase.

---

## Why this fits what already exists

**This extends an existing backend RBAC framework — it does NOT introduce a parallel
one.** Backend at `/home/abrar/odoo/odoo_18/custom/test_user/`; see that repo's
`AUTHORIZATION_IMPLEMENTATION.md`, which already documents this direction (incl. a
recommended `features` payload contract).

### Backend already has (reuse, don't reinvent)

- **`res.mobile.user.group`** (`meta_api_user/models/mobile_role.py`) — the mobile group
  with `code`, `implied_group_ids` (hierarchy: TSM implies SO), and
  `_get_effective_mobile_groups()` that resolves inheritance recursively.
- **`model_access_ids` (`ir.model.access`) + `rule_ids` (`ir.rule`)** on the group —
  gate **data** (which Odoo records a group may read/write), enforced today for the
  contacts API. This is orthogonal to UI gating and stays as-is.
- **5 feature-flag booleans** on the group (`can_view_all_returns`, `can_edit_so_qty`,
  `can_edit_qc_qty`, `can_edit_effective_qty`, `skip_attendance_geolocation`).
- **`MobilePolicy`** (`meta_ss_rest_api/utils/mobile_policy.py`) — enforcement class
  whose `has_model_access(..., default_if_unconfigured=True)` is **exactly the hybrid
  semantic** we chose. Our `enforced` flag just flips that default per resource.

### What's missing (what this plan adds)

A **UI resource layer**: screen/action keys the app owns, granted to groups, so the app
can hide/disable screens and buttons. The backend gates *data* today; it has no concept
of app *screens/buttons* yet.

### App already has (generalize)

- `MobileAuthUser.group` — `{id, code, name}` arrives at login (see
  [mobile_auth_session.dart](lib/data/models/auth/mobile_auth_session.dart)).
- `MobileAuthPermissions` — the 5 flags, mirrored from the group. Become **action
  resources**.
- `AuthProvider.canAccessDealers` / `canAccessPrimarySales` — hardcoded `groupCode == 'so'`
  screen gates. Become **screen resources** (registry lookups).

RBAC **supersedes** the app-side hardcoding: flags → action resources, module gates →
screen resources. Both keep working via a compatibility shim during migration (Phase 1).

---

## Core model: the `enforced` flag (hybrid semantics)

The app evaluates every gate against two sets returned by the backend for the current
user's group:

```
allows(key):
  if key NOT in enforced   -> true      # not yet enforced = visible to all (back-compat)
  else                     -> key in granted
```

Consequences:
- A brand-new screen key the app ships is **visible by default** (it isn't in
  `enforced` until an admin opts it in) → new features never silently disappear.
- Turning on access control for one screen = admin sets `enforced=true` on that key and
  grants it to the right groups. Everything else is untouched.

---

## Resource keys (app-owned, stable, string)

Keys are **owned by the app**, human-readable, hierarchical, and **immutable once
shipped** (Odoo grants reference them). Never reuse Odoo numeric IDs as the identifier.

```
screen.<module>.<name>      screen.sales.order_create
action.<module>.<name>      action.returns.edit_qc_qty
```

### `lib/core/access/access_resources.dart` (single source of truth)

```dart
/// Stable keys. Do NOT rename/remove a shipped key — deprecate instead.
class AppScreen {
  static const dashboard      = 'screen.dashboard';
  static const dealers        = 'screen.contacts.dealers';
  static const routes         = 'screen.routes.list';
  static const primarySales   = 'screen.sales.primary_list';
  static const vanLoading     = 'screen.van_loading.list';
  static const orderCreate    = 'screen.sales.order_create';
  static const returnsList    = 'screen.returns.list';
  static const attendance     = 'screen.hr.attendance';
  static const leave          = 'screen.hr.leave';
  static const expense        = 'screen.hr.expense';
  // …enumerate all screens in Phase 0
}

class AppAction {
  static const returnsViewAll        = 'action.returns.view_all';      // was can_view_all_returns
  static const returnsEditSoQty      = 'action.returns.edit_so_qty';   // was can_edit_so_qty
  static const returnsEditQcQty      = 'action.returns.edit_qc_qty';   // was can_edit_qc_qty
  static const returnsEditEffQty     = 'action.returns.edit_eff_qty';  // was can_edit_effective_qty
  static const attendanceSkipGeo     = 'action.hr.skip_attendance_geo';// was skip_attendance_geolocation
  static const orderConfirm          = 'action.sales.order_confirm';
  static const transferValidate      = 'action.transfers.validate';
  // …enumerate all gated buttons in Phase 0
}

/// Catalog metadata — the payload pushed to Odoo so admins have something to assign.
class AccessResource {
  final String key;      // AppScreen.* / AppAction.*
  final String type;     // 'screen' | 'action'
  final String module;   // 'sales', 'returns', 'hr', …
  final String label;    // human label for the Odoo admin UI
  const AccessResource(this.key, this.type, this.module, this.label);
}

const List<AccessResource> accessCatalog = [
  AccessResource(AppScreen.dealers, 'screen', 'contacts', 'Dealers'),
  AccessResource(AppAction.returnsEditQcQty, 'action', 'returns', 'Edit QC Qty'),
  // …one entry per key
];
```

---

## App architecture

```
Login/permissions response ─► AccessControl (Set<String> enforced, granted)
                                     │  held on AuthProvider, cached in prefs
        ┌────────────────────────────┼────────────────────────────┐
   screen gates                 button gates                   compat shim
   (app_shell nav +             PermissionGate(                canAccessDealers etc.
    route guard)                  resourceKey: AppAction.x)     → access.allows(screen key)
```

### `AccessControl` value object

```dart
class AccessControl {
  final Set<String> enforced;
  final Set<String> granted;
  const AccessControl({this.enforced = const {}, this.granted = const {}});

  bool allows(String key) => !enforced.contains(key) || granted.contains(key);

  factory AccessControl.fromMap(Map<String, dynamic> m) => AccessControl(
    enforced: {...?(m['enforced'] as List?)?.map((e) => e.toString())},
    granted:  {...?(m['granted']  as List?)?.map((e) => e.toString())},
  );
}
```

Held on `AuthProvider` (built from the login response, refreshed on resume/refresh,
persisted next to `userData` so `restoreSession()` works offline). Empty sets =
allow-all = today's behavior.

### `PermissionGate` widget (buttons/sections)

```dart
PermissionGate(
  resourceKey: AppAction.returnsEditQcQty,
  disableInsteadOfHide: true,            // default false = hide
  child: EditQtyButton(...),
)
```
Watches `AuthProvider`; renders `child` when `access.allows(key)`, else the fallback
(`SizedBox.shrink()`) or a disabled variant.

### Screen guard

- **Tab screens** (in `app_shell.dart`'s `IndexedStack`): convert
  [app_shell_config.dart](lib/app/navigation/app_shell_config.dart) nav visibility from
  the three `canAccess*` bools to `access.allows(screenKey)`.
- **Pushed screens**: a helper `AccessGuard.push(context, AppScreen.x, builder)` that
  shows a "You don't have access" panel instead of navigating when disallowed.

### Compatibility shim (keeps existing code working during migration)

```dart
// AuthProvider
bool get canAccessDealers      => access.allows(AppScreen.dealers);
bool get canAccessPrimarySales => access.allows(AppScreen.primarySales);
// MobileAuthPermissions.canEditQcQty consumers → access.allows(AppAction.returnsEditQcQty)
```

---

## Backend (Odoo) — extend the existing framework, don't add a parallel one

Add the UI-resource layer inside `meta_api_user` (where `res.mobile.user.group` lives),
mirroring the existing `model_access_ids` pattern so it inherits through
`implied_group_ids` for free.

### New model + one m2m on the existing group

```
mobile.ui.resource                        -- the catalog the app syncs
  key         char  (unique, indexed)     -- 'screen.sales.order_create'
  res_type    selection [screen, action]
  module      char
  label       char
  enforced    boolean  (default False)    -- hybrid switch: False = visible to all
  active      boolean  (default True)     -- False when app drops a key (grants survive)
  last_seen   char                        -- app version that last synced this key

res.mobile.user.group  (extend)
  ui_resource_ids  m2m -> mobile.ui.resource   -- UI keys granted DIRECTLY to this group
```

**UI grants are per-group and NOT inherited** — this is the deliberate difference from
the data layer. `model_access_ids` / `rule_ids` chain through `implied_group_ids`
(so TSM inherits SO's data rules), but a group's visible screens/buttons =
**exactly its own `ui_resource_ids`**. Do **not** call `_get_effective_mobile_groups()`
here. Each role's screen/button layout is configured explicitly, so a TSM shows only
what TSM is granted even though it inherits SO's data access. UI presentation and data
authorization are separate concerns.

### Extend `MobilePolicy` (mirror `has_model_access`)

```python
def has_ui_access(self, key):
    resource = self.env['mobile.ui.resource'].sudo().search([('key', '=', key)], limit=1)
    if not resource or not resource.enforced:
        return True                                  # unenforced = allow (hybrid default)
    # Direct group only — UI grants are NOT inherited through implied groups.
    return key in self.ensure_group().ui_resource_ids.mapped('key')
```

The app receives precomputed sets (below) rather than calling this per key, but the same
method backs Phase 4 endpoint enforcement.

### Login/permissions payload (extend the session serializer)

The login response is built in `meta_api_user/models/mobile_auth_session.py`
(`login_and_create_session`) — the same place the `group`/`permissions` object is
assembled today. Add an `access` block:

```json
"access": {
  "enforced": ["screen.contacts.dealers", "action.returns.edit_qc_qty"],
  "granted":  ["action.returns.edit_qc_qty"]
}
```
- `enforced` = all currently-enforced resource keys (global).
- `granted`  = keys granted **directly to the caller's own group** (`res.mobile.user.group`),
  NOT inherited through implied groups.
- App rule stays: `allows(key) = key not in enforced || key in granted`.

### Endpoints (`/api/v1`, per repo convention)

```
POST /access/catalog/sync         (admin/integration group only)
  body:   { app_version, resources: [{key, type, module, label}] }
  action: upsert mobile.ui.resource by key; mark keys absent from payload active=False
          (never delete → grants survive); returns { added, updated, deactivated }

GET  /access/permissions          (authenticated)
  returns the same `access` block as login, for re-fetch on resume/refresh.
```

Admin assigns grants on the existing **Mobile User Group** form (a new `UI Resources`
tab next to `Model Access` / `Record Rules`), and toggles `enforced` on
`mobile.ui.resource` records.

---

## Data lifecycle

- **Catalog sync:** admin/dev-triggered, or automatic once per app-version bump
  (compare stored version, debounce). Requires the caller to be in an admin group.
  Never runs on ordinary user launches.
- **Permissions fetch:** embedded in the login response (first paint) + re-fetched on
  app resume and after token refresh. Cached in `shared_preferences` alongside
  `userData`; `AuthProvider.restoreSession()` loads it so gating works offline with the
  last-known grants.

---

## Backend enforcement (required follow-up — the real security)

UI gating hides controls; it does not stop a modified client. Each business endpoint
must map to an action key and check the caller's group grant **before** executing —
reusing the `MobilePolicy.has_ui_access` method added above:

```python
policy = MobilePolicy(mobile_user)
if not policy.has_ui_access('action.transfers.validate'):
    raise AccessDenied(...)
# (wrap as a decorator once the pattern is proven)
```

The backend already enforces **data** access (model access + record rules via
`MobilePolicy`) for the contacts API; this adds **action** enforcement on the same
policy object. Lands with / after the JWT-enforcement P0 in `FIXES.md` — once the server
derives the mobile user/group from the bearer token instead of trusting the
`employee_id` request param, `MobilePolicy` can be built from the token on every call.

---

## Rollout phases (each is independently shippable and regression-safe)

**Phase 0 — Plumbing, allow-all.**
Build `access_resources.dart` (enumerate every screen + gated action), `AccessControl`,
`PermissionGate`, the screen guard, and the prefs caching. Wire them but with empty
`enforced`/`granted` sets → `allows()` returns true everywhere. **Zero behavior change.**
Verify build + smoke test.

**Phase 1 — Migrate existing gates into the registry (behavior-identical).**
Replace hardcoded `canAccessDealers` / `canAccessPrimarySales` and the 5
`MobileAuthPermissions` flags with registry keys via the compat shim. Mark exactly those
keys `enforced`, and seed grants that reproduce current behavior (SO group excluded from
dealers/primary, etc.). Confirm SO and manager logins behave **exactly** as before.

**Phase 2 — Catalog sync + admin assignment.**
Ship `POST /access/catalog/sync` and the Odoo grant admin view. Push the catalog. Now
admins can assign — but only the Phase-1 keys are enforced, so nothing else changes.

**Phase 3 — Expand coverage.**
Add `PermissionGate` / guards to more screens and buttons, flipping each resource to
`enforced` one at a time as it's configured. Incremental, reversible per resource.

**Phase 4 — Backend enforcement.**
Add the `@requires_access` decorator to business endpoints (with JWT-derived group).

---

## Resolved (from reading the backend)

- **Group source of truth:** `res.mobile.user.group` (custom mobile group, not
  `res.groups`). `MobileAuthGroup.id` in the login response = a `res.mobile.user.group`
  id. `ui_resource_ids` hangs off this model.
- **One group per user; UI grants NOT inherited.** `res.mobile.user` has a single
  `group_id`. `granted` = that group's own `ui_resource_ids` only. Data access still
  inherits via `implied_group_ids` (unchanged), but UI screen/action visibility is
  configured explicitly per group — the two are intentionally decoupled.
- **Hybrid semantics already exist:** `MobilePolicy`'s `default_if_unconfigured=True` is
  the same allow-until-configured behavior; the `enforced` flag flips it per resource.

## Still open

- **Enforced-flag granularity:** global per resource (plan's assumption, simpler) vs
  per-group. Keep global unless a real case needs otherwise.
- **Screen ↔ data consistency:** some screens map 1:1 to a model already gated by
  `model_access_ids` (e.g. `screen.contacts.dealers` ↔ `res.partner` distributor rule).
  Decide per screen: explicit UI grant (flexible, plan's default) vs auto-derive
  visibility from existing model access (less config, but only works for 1:1 screens).
- **Payload shape:** flat `enforced`/`granted` sets (this plan) vs the richer per-feature
  `{visible,read,create,write,delete}` map recommended in the backend's
  `AUTHORIZATION_IMPLEMENTATION.md`. Flat sets are enough for show/hide; adopt the rich
  map only if buttons need finer CRUD distinctions than a single action key gives.
```

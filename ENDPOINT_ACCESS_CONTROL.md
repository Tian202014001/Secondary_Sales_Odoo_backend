# Endpoint Operation Access Control

This document describes how the mobile API endpoints are protected today and which endpoints are intentionally left without UI-resource operation gates.

The backend does not use Odoo backend menu ACLs as the primary mobile-app permission boundary. Mobile endpoint authorization is based on the app-synced UI/action resource catalog in `mobile.ui.resource`.

## Protection Model

Most mobile business endpoints use this sequence:

1. The route is an authenticated Odoo JSON route, usually `auth="user"`.
2. The endpoint calls `get_mobile_api_context(payload, ...)`.
3. `get_mobile_api_context` validates the `Authorization: Bearer <token>` mobile JWT through `mobile.auth.session`.
4. The trusted `res.mobile.user` is resolved from the token.
5. If the mobile user has an employee, incoming `employee_id` is overwritten with the token employee id.
6. The endpoint calls one of the fail-closed UI-resource helpers.
7. Domain/object-level checks still need to be handled by the endpoint's business logic.

Core files:

```text
meta_ss_rest_api/utils/common.py
meta_ss_rest_api/utils/access_keys.py
```

Important helpers:

| Helper | Purpose |
|---|---|
| `require_ui_access(mobile_user, key)` | Denies unless `key` exists as an active `mobile.ui.resource`, has `module_ids`, and is in the user's effective resources. |
| `require_any_ui_access(mobile_user, keys)` | Allows when at least one listed key is granted. |
| `require_sale_type_access(...)` | Chooses primary/secondary key from `payload.sale_type` or `payload.type`. |
| `require_contact_type_access(...)` | Chooses distributor/outlet key from `payload.customer_type` or `payload.type`. |

Important behavior:

- Endpoint authorization is fail-closed.
- Unknown resource keys are denied.
- Active resources without module mapping are denied.
- Mobile users without a group are denied.
- UI visibility is not treated as security by itself; backend endpoint gates are authoritative.
- These gates are function-level permissions. They do not replace record-scope checks.

## Protected Endpoints

### Sales Orders

| Endpoint group | Required resource |
|---|---|
| Primary order list | `screen.primary_sale.orders.list` |
| Primary order detail / print | `screen.primary_sale.orders.detail` |
| Primary order create / update | `action.primary_sale.orders.create` |
| Primary order confirm | `action.primary_sale.orders.confirm` |
| Primary order cancel | `action.primary_sale.orders.cancel` |
| Secondary order list | `screen.secondary_sale.orders.list` |
| Secondary order detail / print | `screen.secondary_sale.orders.list` |
| Secondary order create / update | `action.secondary_sale.orders.create` |
| Secondary order confirm | `action.secondary_sale.orders.confirm` |
| Secondary order cancel | `action.secondary_sale.orders.cancel` |
| Sales mediums/reference for order creation | Any of `action.primary_sale.orders.create`, `action.secondary_sale.orders.create` |

Controllers:

```text
meta_ss_sales/controllers/sales.py
meta_ss_sales/controllers/sale_order_details.py
```

### Deliveries

| Endpoint group | Required resource |
|---|---|
| Primary delivery list | `screen.primary_sale.deliveries.list` |
| Primary delivery prepare/lots/auto-assign/action | `action.primary_sale.deliveries.validate` |
| Secondary delivery list | `screen.secondary_sale.deliveries.list` |
| Secondary delivery prepare/lots/auto-assign/action | `action.secondary_sale.deliveries.validate` |

Controller:

```text
meta_ss_sales/controllers/deliveries.py
```

### Returns

| Endpoint group | Required resource |
|---|---|
| Primary return list/detail | `screen.primary_sale.returns.list` |
| Primary return prepare/products/lots/create | `action.primary_sale.returns.create` |
| Primary return update/save | `action.primary_sale.returns.save` |
| Primary return validate | `action.primary_sale.returns.validate` |
| Primary return cancel | `action.primary_sale.returns.cancel` |
| Secondary return list/detail | `screen.secondary_sale.returns.list` |
| Secondary return prepare/products/lots/create | `action.secondary_sale.returns.create` |
| Secondary return update/save | `action.secondary_sale.returns.save` |
| Secondary return validate | `action.secondary_sale.returns.validate` |
| Secondary return cancel | `action.secondary_sale.returns.cancel` |

Controller:

```text
meta_ss_transfer/controllers/returns.py
```

### Scraps

| Endpoint group | Required resource |
|---|---|
| Primary scrap list/detail | `screen.primary_sale.scraps.list` |
| Primary scrap prepare/products/lots/create | `action.primary_sale.scraps.create` |
| Primary scrap update/save | `action.primary_sale.scraps.save` |
| Primary scrap validate | `action.primary_sale.scraps.validate` |
| Primary scrap cancel | `action.primary_sale.scraps.cancel` |
| Secondary scrap list/detail | `screen.secondary_sale.scraps.list` |
| Secondary scrap prepare/products/lots/create | `action.secondary_sale.scraps.create` |
| Secondary scrap update/save | `action.secondary_sale.scraps.save` |
| Secondary scrap validate | `action.secondary_sale.scraps.validate` |
| Secondary scrap cancel | `action.secondary_sale.scraps.cancel` |

Controller:

```text
meta_ss_transfer/controllers/scraps.py
```

### Contacts

| Endpoint group | Required resource |
|---|---|
| Distributor list/detail/history | `screen.primary_sale.distributors.list` or `screen.primary_sale.distributors.detail` depending on route context |
| Distributor create/update | `action.primary_sale.distributors.create` |
| Outlet list/detail/history | `screen.secondary_sale.outlets.list` |
| Outlet create | `action.secondary_sale.outlets.create` |
| Outlet update | `screen.secondary_sale.outlets.edit` |
| Contact endpoint without explicit customer type | Any relevant distributor/outlet list key |

Controller:

```text
meta_ss_contact/controllers/contacts.py
```

### Routes And Visits

| Endpoint group | Required resource |
|---|---|
| Route list | `screen.secondary_sale.routes.list` |
| Route detail | `screen.secondary_sale.routes.detail` |
| Route create/update | `action.secondary_sale.routes.create` |
| Add/remove route outlet | `action.secondary_sale.routes.add_outlet` |
| Visit list/today | `screen.secondary_sale.visits.list` |
| Visit create/check-in | `action.secondary_sale.visits.check_in` |
| Visit update/check-out | `action.secondary_sale.visits.check_out` |

Controller:

```text
meta_ss_route_management/controllers/routes.py
```

### Virtual Transfers And Van Loading

| Endpoint group | Required resource |
|---|---|
| Virtual transfer prepare/products/lots/auto-assign/create/update | `action.secondary_sale.transfers.create` |
| Virtual transfer list | `screen.secondary_sale.transfers.list` |
| Virtual transfer detail | `screen.secondary_sale.transfers.detail` |
| Virtual transfer validate | `action.secondary_sale.transfers.validate` |
| Virtual transfer cancel | `action.secondary_sale.transfers.cancel` |
| Van loading target list | `screen.secondary_sale.van_loading.list` |

Controllers:

```text
meta_ss_transfer/controllers/virtual_transfers.py
meta_ss_rest_api/controllers/van_loading.py
```

### Employees / Sales Officers

| Endpoint group | Required resource |
|---|---|
| Sales officer list | `screen.dashboard.sales_officers.list` |
| Sales officer detail | `screen.dashboard.sales_officers.detail` |
| Sales officer create/update | `action.dashboard.sales_officers.create` |

Controller:

```text
meta_ss_employee/controllers/employees.py
```

### Attendance

| Endpoint group | Required resource |
|---|---|
| Attendance status | `screen.hr.attendance` |
| Attendance history | `screen.hr.attendance` |
| Attendance check-in/check-out action | `screen.hr.attendance` |

Controller:

```text
meta_ss_attendance/controllers/attendance.py
```

Note: there is no separate punch action key in the current app catalog, so the attendance screen key protects the attendance action endpoint for now.

### My Team / Dashboard Checkpoints

| Endpoint group | Required resource |
|---|---|
| Manager my-team list | `screen.module.dashboard` |
| Employee checkpoints | `screen.module.dashboard` |

Controller:

```text
meta_ss_location_tracking/controllers/location_api.py
```

### Expense

| Endpoint group | Required resource |
|---|---|
| Expense categories/list/drafts | `screen.accounts.expense` |
| Expense sheet list/detail | `screen.accounts.expense` |
| Expense sheet create | `action.accounts.expense.create` |

Controller:

```text
meta_ss_expense/controllers/expense.py
```

### Leave

| Endpoint group | Required resource |
|---|---|
| Leave types/list | `screen.hr.leave` |
| Leave request/create | `action.hr.leave.create` |

Controller:

```text
meta_ss_leave_request/controllers/leave_api.py
```

## Intentionally Not UI-Resource Gated

These endpoints are not protected by `require_ui_access`. Some are public auth-flow endpoints; most are still authenticated by Odoo route auth and/or mobile bearer-token context.

### Auth Flow

| Endpoint | Reason |
|---|---|
| `/api/v1/auth/bootstrap-session` | Intentional pre-login/session bootstrap flow. |
| `/api/v1/auth/login` | Login must be reachable before mobile identity exists. |
| `/api/v1/auth/refresh` | Token refresh flow. |
| `/api/v1/auth/logout` | Session logout/revocation flow. |
| Legacy `/api/mobile/*` aliases | Compatibility auth aliases. |

### Access Catalog And Permission Bootstrap

| Endpoint | Reason |
|---|---|
| `/api/v1/access/permissions` | App needs this to learn effective resources and render UI. |
| `/api/v1/access/catalog/sync` | Catalog sync endpoint; guarded by its own access-management logic, not per-resource operation keys. |

### Device Infrastructure

| Endpoint | Reason |
|---|---|
| Mobile device register/unregister endpoints | Push-token infrastructure for authenticated users, not a business operation. |

### Background Telemetry

| Endpoint | Reason |
|---|---|
| `/api/v1/employee/location/sync` | Authenticated background location telemetry tied to the token employee; not a user-triggered UI operation. |

### Shared Reference Feeds

| Endpoint | Reason |
|---|---|
| `/api/v1/products` | Shared reference feed, not a business operation. |
| `/api/v1/products/<product_id>/available-lots` | Shared inventory/reference lookup. |
| `/api/v1/locations` | Shared reference feed. |
| `/api/v1/warehouses` | Shared reference feed. |
| Warehouse location/lots helper endpoints | Shared reference/inventory lookup. |

### Manager Approval Actions

| Endpoint | Reason |
|---|---|
| `/api/v1/hr/expense/approve` | Existing Odoo employee-manager backend logic controls approval authority. |
| `/api/v1/hr/expense/refuse` | Existing Odoo employee-manager backend logic controls refusal authority. |
| `/api/v1/hr/leave/action` | Existing Odoo employee-manager backend logic controls approval/refusal authority. |

## Authenticated But Still Needs Review

These endpoints currently use authenticated routes but are not yet covered by the UI-resource operation gate table above:

| Endpoint group | Current concern |
|---|---|
| `meta_ss_transfer/controllers/virtual_locations.py` | Van-loading location setup endpoints are operational setup endpoints. If the app exposes them to mobile users, they should be gated with the existing secondary van-loading/location keys or moved to an admin-only backend flow. |
| Barikoi/map proxy endpoints | They are utility/map endpoints rather than sales operations. If usage cost or data exposure matters, add a dedicated map/config key. |

## Verification Snapshot

Current verification after implementation:

```text
python3 -m py_compile ... passed for touched helpers/controllers
AccessKey constants: 76
Missing AccessKey constants in active ss_22 mobile_ui_resource catalog: 0
Active ss_22 mobile_ui_resource keys: 90
```

The remaining gap is automated test coverage. The next step should be an endpoint authorization test matrix plus Odoo tests for allowed/denied cases.

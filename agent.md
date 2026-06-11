# Secondary Sales Odoo + Flutter Agent Context

This workspace contains custom Odoo 18 modules for a Secondary Sales system and a Flutter mobile app that consumes the APIs.

## 1. Workspace

Odoo custom addons path:

```text
/home/abrar/odoo/odoo_18/custom/test_user
```

Flutter app path:

```text
/home/abrar/AndroidStudioProjects/secondary_sales
```

Current Odoo database used during development:

```text
s_sales
```

Local Odoo URL:

```text
http://127.0.0.1:8069
```

For Android emulator only, `10.0.2.2:8069` may be needed. For Linux desktop Flutter builds, use `127.0.0.1:8069`.

## 2. Main Business Flow

The system supports primary sales first, then secondary sales later.

Primary sales flow:

1. Mobile user logs in.
2. Login returns the linked `hr.employee`.
3. TSM creates a primary sale order for a distributor.
4. Products are added to the order.
5. Sale order is confirmed.
6. Odoo creates a delivery.
7. Mobile app opens the sale order detail.
8. User validates delivery, including partial delivery and lot-wise quantity if needed.
9. Delivery validation updates Odoo stock and sale order delivered quantities.

Planned virtual inventory flow:

1. Primary sale delivery moves stock to the distributor customer/delivery location from partner master data.
2. Virtual transfer moves stock from the distributor customer location to the employee Van Loading Location.
3. Secondary sales later consume stock from the employee Van Loading Location.

## 3. Odoo Modules

### `meta_api_user`

Mobile authentication module.

Important models:

- `res.mobile.user`
- `res.mobile.user.group`
- `mobile.auth.session`

Important endpoints:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

Legacy aliases still exist:

- `/api/mobile/login`
- `/api/mobile/refresh`
- `/api/mobile/logout`

Current notes:

- The old model `res.mobile.role` was renamed to `res.mobile.user.group`.
- `res.mobile.user.group_id` is the field used on mobile users.
- Do not reintroduce `role_id`.
- Login response keeps `user.role` as a compatibility string and also returns structured `user.group`.
- Auth currently returns JWT tokens, but most business APIs do not yet validate JWT.

### `meta_ss_rest_api`

Business REST/JSON-RPC API module for the Flutter app.

Docs:

- `meta_ss_rest_api/api_list.md`: quick endpoint list.
- `meta_ss_rest_api/api_documentation.md`: request/response examples.

Keep APIs file-wise separated:

- controllers in `meta_ss_rest_api/controllers/`
- logic helpers in `meta_ss_rest_api/utils/`

Do not put all APIs or all logic into one file.

Current implemented areas:

- contacts/dealers/outlets
- products
- primary sales
- sale order details
- delivery prepare/validate
- warehouses and available lots
- routes and employee outlets

Security rule for later:

- Do not trust `employee_id` from the app after JWT validation is wired.
- Validate `Authorization: Bearer <token>`.
- Derive employee from `meta_api_user`.
- Only allow records belonging to that employee.

Current temporary behavior:

- Business APIs use `employee_id` from JSON-RPC `params`.
- Primary sale detail/cancel/delivery APIs verify that the order belongs to `sale.order.so_employee_id`.

### `meta_ss_sales`

Sale order extensions for secondary sales.

Important fields:

- `sale.order.sale_type`
- `sale.order.so_employee_id`
- `sale.order.route_id`
- `stock.picking.so_employee_id`, related to `sale_id.so_employee_id`

Primary sale APIs rely on `so_employee_id` for employee scoping.

### `meta_ss_route_management`

Route and outlet assignment module.

Important concepts:

- Employee can be assigned multiple routes.
- `sale.route.line` is intended to be the single user-facing source for route outlets.
- Route planning exists as an optional feature, not mandatory.
- Mobile app later lets an employee select a route for the day or use a management-predefined route.

Important models:

- `sale.route`
- `sale.route.line`
- `route.visit.plan`
- `route.visit.plan.line`
- `hr.employee` extension with distributor and route assignment fields

### `meta_ss_contact`

Partner/contact extension.

Important fields:

- `res.partner.customer_type`
  - `distributor`
  - `outlet`
- `res.partner.default_location_id`

Dealers in the Flutter app mean distributors, which are `res.partner` records where `customer_type = distributor`.

### `meta_ss_transfer`

Virtual inventory transfer module.

Current state:

- Adds custom picking type: `Virtual Location Transfer`.
- Extends `stock.picking` with distributor and destination location fields.

Current model fields:

- `stock.picking.ss_distributor_id`
- `stock.picking.ss_destination_location_id`
- `stock.picking.ss_is_virtual_location_transfer`

Current/planned improvement:

- Add/use secondary-sales-specific fields on `stock.location`:
  - `ss_location_type`, currently `odoo` or `van_loading`
  - `ss_employee_id`
  - `ss_distributor_id`
- Van Loading Locations are created under the technical parent `Secondary Sales Virtual Locations`.
- The app should not ask users to select a parent warehouse/location.
- Add/use APIs for Van Loading Location creation and assignment.
- Add APIs for virtual transfer creation/validation.
- Virtual transfers currently derive source from `employee.distributor_contact_id.property_stock_customer`.
- Virtual transfer destination must be a `stock.location` with `ss_location_type = van_loading`, assigned to the same employee and distributor.

## 4. API Conventions

Business endpoints use Odoo JSON-RPC:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {},
  "id": 1
}
```

Return shape:

```json
{
  "success": true,
  "api_version": "v1",
  "message": "Message here.",
  "data": {}
}
```

Errors should use the existing `error_response()` helper in `meta_ss_rest_api/utils/common.py`.

When adding endpoints:

- Add controller file under `controllers/`.
- Add helper file under `utils/`.
- Register controller in `controllers/__init__.py`.
- Add docstring with request and response examples.
- Update `api_list.md`.
- Update `api_documentation.md`.

## 5. Current App Structure

Flutter app path:

```text
/home/abrar/AndroidStudioProjects/secondary_sales
```

Important app areas:

- `lib/services/api_service.dart`
- `lib/services/auth_service.dart`
- `lib/providers/auth_provider.dart`
- `lib/providers/primary_sale_provider.dart`
- `lib/screens/auth/`
- `lib/screens/tsm/`
- `lib/models/`

Current UI concepts:

- `Home`: primary sales dashboard with search, date filter, status filter.
- `Order`: distributor selection and primary sale order creation.
- `Dealers`: distributor management.
- `Routes`: route/outlet work.

Recommended future UI:

- Add an `Inventory` area for:
  - Van Loading Locations
  - virtual transfers
  - distributor stock
  - employee stock

Do not hide Van Loading Location setup under `Dealers`, because users will not expect inventory setup inside distributor management.

## 6. Flutter Development Rules

Keep app files separated:

- models in `lib/models/`
- services in `lib/services/`
- providers in `lib/providers/`
- screens in `lib/screens/...`
- reusable widgets in `lib/widgets/` if needed

Do not put large workflows into one Dart file.

After Flutter edits, run:

```text
dart format .
flutter analyze
```

Because the app is outside the Odoo writable root, shell commands in the Flutter directory may need elevated permission in restricted environments.

## 7. Odoo Development Rules

Use Odoo conventions:

- model fields in `models/`
- views in `views/`
- data records in `data/`
- access rights in `security/ir.model.access.csv`
- route controllers in `controllers/`
- reusable API logic in `utils/`

After Python/XML edits:

```text
python3 -m py_compile <changed_python_files>
python3 -c "import pathlib, xml.etree.ElementTree as ET; [ET.parse(str(p)) for p in pathlib.Path('<module>').rglob('*.xml')]; print('xml ok')"
```

Then upgrade the affected Odoo module from Apps or command line.

## 8. Important Design Decisions Already Made

- Primary sale orders are tied to `sale.order.so_employee_id`.
- App should use employee from login, not manually entered employee ids long term.
- For now, `employee_id` is still passed in API params until JWT business API validation is implemented.
- Delivery validation supports partial delivery.
- Delivery validation supports lot-wise allocation.
- `sale.route.line` should be the single user-facing route outlet source.
- Route visit planning is optional.
- Virtual transfer should be linked to delivery for tracking, but source delivery should remain optional for flexibility.
- Virtual locations should be managed as inventory/setup data, preferably under an app `Inventory` section.

## 9. Common Pitfalls

- Do not use removed `role_id`; use `group_id`.
- Do not return Odoo recordsets directly in JSON responses.
- Do not trust app-provided `employee_id` once JWT validation is added.
- Do not put Van Loading Location creation only under Dealers; it is inventory setup.
- Do not mix unrelated models into one Python file when the module already has separate files.
- Do not create one giant Flutter screen/service file.
- For Linux Flutter app, `127.0.0.1:8069` is correct; `10.0.2.2` is for Android emulator.

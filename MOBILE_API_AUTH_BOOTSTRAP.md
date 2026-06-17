# Mobile API Authentication Bootstrap

## Problem

The mobile app uses a custom Odoo model, `res.mobile.user`, for real mobile users and JWT tokens. The original API routes were `auth="public"` so they could be called without an Odoo session.

That created two problems:

- Odoo still needs a database before it can build `request.env` and access `res.mobile.user`.
- Public business APIs could be called without an authenticated Odoo user, and several endpoints trusted `employee_id` from the request payload.

In a multi-database server without `dbfilter`, the first mobile request has no Odoo DB/session. The goal is:

```text
First install:
Mobile user enters server IP/URL once.
Mobile app lists databases.
Mobile user selects one DB and confirms.
The app creates an Odoo session using the configured internal integration user.

Normal use:
Mobile user only enters custom mobile email/password.
The app reuses the cached server, DB, and Odoo session cookie.
```

## Final Architecture

There are now two authentication layers:

```text
Odoo session
    Purpose: selected DB + authenticated technical Odoo user for auth="user" routes.

Custom mobile JWT
    Purpose: real mobile identity, employee mapping, mobile permissions.
```

The mobile app does not call `/web/session/authenticate` anymore for this flow.

For first-run setup, it calls:

```text
POST /web/database/list
POST /api/v1/auth/bootstrap-session
```

After setup, normal mobile login calls:

```text
POST /api/v1/auth/login
```

with the cached DB and custom mobile credentials.

The bootstrap-session controller:

1. Reads `db` from JSON body, query string, or existing session.
2. Opens that database registry manually.
3. Reads the configured Mobile API integration user from `meta_api_user.integration_user_id`.
4. Creates an Odoo `session_id` cookie for that integration user.

The login controller validates the custom `res.mobile.user` login/password and returns the custom mobile JWT access token and refresh token. It can also refresh the Odoo session cookie, which helps when the cached Odoo session has expired.

Business APIs then require both:

```http
Cookie: session_id=<odoo session>
Authorization: Bearer <mobile access token>
```

## Required Odoo Config

Because `/api/v1/auth/bootstrap-session` and `/api/v1/auth/login` must be callable before Odoo has selected a DB, `meta_api_user` must be loaded server-wide.

In `odoo.conf`:

```ini
server_wide_modules = base,web,meta_api_user
```

Equivalent CLI test command:

```bash
python3 odoo/odoo-bin -c odoo.conf --load=web,meta_api_user
```

Why this is necessary:

- Odoo route matching happens before the controller reads the JSON body.
- Without an existing DB/session, DB-specific custom module routes are not loaded.
- Without `server_wide_modules`, `/api/v1/auth/bootstrap-session` or `/api/v1/auth/login` can return `404 Not Found` as first requests.

This does not require `dbfilter`. `list_db` can remain enabled if the server needs database listing.

## First-Run Setup Requests

### List Databases

```http
POST /web/database/list
Content-Type: application/json
```

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {},
  "id": 1
}
```

### Bootstrap Odoo Session

```http
POST /api/v1/auth/bootstrap-session?db=ss_test
Content-Type: application/json
```

```json
{
  "db": "ss_test"
}
```

The response sets an Odoo session cookie:

```http
Set-Cookie: session_id=<odoo-session-id>; HttpOnly; Path=/
```

The mobile app stores:

- server base URL
- selected DB
- `session_id` cookie

## App-Side Cached Connection

The Flutter app stores the selected connection in `SharedPreferences`, not in Odoo.

Storage keys:

```text
odoo_base_url
odoo_db_name
odoo_session_id
```

These are defined in:

```text
lib/core/constants.dart
```

When the user confirms the first-run setup screen, the app:

1. Calls `/api/v1/auth/bootstrap-session` with the selected DB.
2. Reads `session_id` from the `Set-Cookie` response header.
3. Saves the normalized server URL, selected DB, and `session_id`.

On the next app launch, `main.dart` calls `AppConstants.initialize()` before creating providers. That reloads the cached server URL and DB, so the setup screen is skipped and the normal mobile login screen is shown.

Mobile logout clears mobile tokens, but keeps the cached Odoo connection details. This means the user does not need to enter server IP or DB again after logout.

## Internal User Password

The mobile app does not know, store, or send the internal Odoo user's password.

The internal user session is created server-side inside Odoo:

```python
env = api.Environment(cr, SUPERUSER_ID, {})
integration_user = env["mobile.auth.session"].sudo()._get_integration_user()
self._bootstrap_odoo_session(db_name, integration_user)
```

`_get_integration_user()` reads the configured user from:

```text
ir.config_parameter: meta_api_user.integration_user_id
```

Because this code runs inside Odoo as trusted server-side code, it can read the configured integration user and create an Odoo session for that user without receiving the user's password from the mobile app.

The selected user must still be a valid active internal Odoo user configured in Odoo Settings.

## Mobile Login Request

The login endpoint is plain HTTP JSON, not JSON-RPC.

```http
POST /api/v1/auth/login
Content-Type: application/json
```

```json
{
  "db": "ss_test",
  "login": "test@gmail.com",
  "password": "1234",
  "device_id": "phone-001",
  "device_info": "Android"
}
```

The `db` value may also be passed in the URL:

```text
/api/v1/auth/login?db=ss_test
```

If `db` is missing, the endpoint returns `400`.

## Mobile Login Response

The response sets an Odoo session cookie:

```http
Set-Cookie: session_id=<odoo-session-id>; HttpOnly; Path=/
```

The JSON body returns the custom mobile tokens:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<opaque-refresh-token>",
  "token_type": "Bearer",
  "expires_in": 900,
  "user": {
    "id": 1,
    "name": "test",
    "role": "Sales Officer",
    "group": {
      "id": 1,
      "code": "so",
      "name": "Sales Officer"
    },
    "permissions": [],
    "employee_id": 6,
    "employee_name": "Employee Name"
  }
}
```

The mobile app must store/update:

- `session_id` cookie
- `access_token`
- `refresh_token`

## Business API Request

Business APIs remain Odoo JSON routes, so send JSON-RPC-style payloads.

```http
POST /api/v1/products?db=ss_test
Cookie: session_id=<odoo-session-id>
Authorization: Bearer <mobile-access-token>
Content-Type: application/json
```

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "page": 1,
    "page_size": 20
  },
  "id": 1
}
```

The `db` query parameter is useful for clarity in a multi-DB setup, but the Odoo session cookie is already tied to the DB.

## Code Changes

### `meta_api_user/controllers/mobile_auth_controller.py`

Changed `/api/v1/auth/login` from:

```python
auth="user"
```

to:

```python
auth="none"
```

This makes login callable before an Odoo session exists.

Added:

- `_request_db(payload)`
- `_bootstrap_with_integration_user(db_name)`
- `_login_with_mobile_user(db_name, payload)`
- `_bootstrap_odoo_session(db_name, user)`

These methods manually open the selected DB, create the Odoo session cookie for the configured integration user, and authenticate the custom mobile user when `/api/v1/auth/login` is called.

`/api/v1/auth/refresh` and `/api/v1/auth/logout` remain:

```python
auth="user"
```

because after login the mobile app should already have an Odoo session cookie.

### `meta_ss_rest_api/utils/common.py`

Added:

```python
get_mobile_api_context(payload=None, required_permission=None, require_employee=False)
```

This helper:

- validates `Authorization: Bearer <token>`
- checks optional mobile permission
- requires a mapped employee when needed
- replaces request `employee_id` with `mobile_user.employee_id.id`
- returns the configured integration-user environment

This prevents mobile clients from impersonating another employee by changing `employee_id` in the request payload.

### Business Controllers

Changed business API routes from:

```python
auth="public"
```

to:

```python
auth="user"
```

Updated controllers to call `get_mobile_api_context(...)` before doing business work.

Affected controller files:

- `meta_ss_rest_api/controllers/products.py`
- `meta_ss_rest_api/controllers/locations.py`
- `meta_ss_rest_api/controllers/warehouses.py`
- `meta_ss_contact/controllers/contacts.py`
- `meta_ss_employee/controllers/employees.py`
- `meta_ss_route_management/controllers/routes.py`
- `meta_ss_transfer/controllers/virtual_locations.py`
- `meta_ss_transfer/controllers/virtual_transfers.py`
- `meta_ss_sales/controllers/sales.py`
- `meta_ss_sales/controllers/sale_order_details.py`
- `meta_ss_sales/controllers/deliveries.py`

### `meta_ss_rest_api/api_documentation.md`

Updated the security section to document:

- login bootstraps the Odoo session
- business APIs are `auth="user"`
- business APIs require mobile bearer tokens
- employee scope comes from the JWT, not request payload

## Integration User Requirement

The login bootstrap uses the Mobile API integration user configured in:

```text
Settings -> Mobile API -> Backend Integration User
```

Technically this is stored in:

```text
meta_api_user.integration_user_id
```

If it is not configured, login fails with a validation error:

```text
Configure a Mobile API backend integration user first.
```

The integration user should be:

- internal Odoo user
- active
- not admin unless absolutely necessary
- granted only the groups needed by mobile API operations

## Test Result

Tested against local DB:

```text
ss_test
```

First attempt without server-wide loading:

```text
POST /api/v1/auth/login
-> 404 Not Found
```

Reason: custom route was not registered before DB/session selection.

Second attempt with:

```bash
--load=web,meta_api_user
```

Login succeeded:

```text
POST /api/v1/auth/login?db=ss_test
-> 200 OK
-> Set-Cookie: session_id=...
-> access_token + refresh_token returned
```

Then business API succeeded:

```text
POST /api/v1/products?db=ss_test
Cookie: session_id=...
Authorization: Bearer <access_token>
-> 200 OK
-> Products fetched successfully
```

## Important Notes

- The mobile user still does not enter Odoo internal-user credentials.
- The DB name is still required because `res.mobile.user` records live inside a specific DB.
- The DB name can come from app environment selection, not a visible user input.
- The Odoo session is a technical session only.
- The mobile JWT remains the real identity and permission layer.
- Business APIs should never trust `employee_id` directly from the mobile payload.

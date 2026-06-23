# Mobile Authorization Implementation

## Scope

This document summarizes the current authorization work for the secondary sales mobile app and Odoo backend.

Implemented scope:

- Mobile-group implied inheritance.
- Effective model access and effective record-rule visibility in Odoo.
- Contact/distributor API authorization enforcement.
- App-side Dealer menu visibility based on the logged-in mobile user's group code.

Not implemented yet:

- Generic authorization enforcement for every endpoint.
- Offline-first behavior.
- Full feature-permission payload in the mobile login/API response.

## Backend Implementation

### Mobile Group Inheritance

Model: `res.mobile.user.group`

Each mobile group can imply other mobile groups through `implied_group_ids`.

Example:

- `Territory Sales Manager` implies `Sales Officer`.
- TSM effectively inherits SO access and SO record rules.
- TSM can then receive extra access/rules on top.

The backend now resolves effective groups recursively, so access and rules are calculated from:

```text
current group + all implied groups
```

### Effective Access Visibility

Added read-only tabs in the Mobile User Group form:

- `Effective Access`
- `Effective Rules`

These tabs show the inherited result from the current group and its implied groups.

Example:

If TSM implies SO, and SO has outlet access/rule, then TSM's own `Model Access` and `Record Rules` tabs may be empty, but the `Effective Access` and `Effective Rules` tabs will show the inherited SO permissions.

### Contact API Enforcement

The contacts API now checks mobile authorization for `res.partner`.

Implemented for:

- Contact list.
- Contact create.
- Contact detail.
- Contact update.
- Contact history.

The authorization flow is:

1. Authenticate mobile user from the bearer token.
2. Read the user's mobile group.
3. Resolve effective groups.
4. Check effective model access for the operation.
5. Switch contact ORM operations to a controlled sudo environment.
6. Apply effective record-rule domain.
7. Return only allowed records or block forbidden operations.

The controlled sudo step is intentional for this API. The configured Mobile API integration user is only the backend execution user. It does not define the mobile user's business permissions. Business permissions are defined by `res.mobile.user.group` model access and record rules, then enforced explicitly by the contacts controller.

For distributor list:

- Endpoint: `POST /api/v1/contacts`
- Distributor request: `customer_type = "distributor"`
- SO with outlet-only rule is blocked from distributor list.
- TSM with distributor rule can access distributor list.

## App Implementation

Flutter app path:

```text
/home/abrar/AndroidStudioProjects/secondary_sales
```

### Parsed Mobile Group

The login response already includes:

```json
{
  "user": {
    "role": "Sales Officer",
    "group": {
      "id": 1,
      "code": "so",
      "name": "Sales Officer"
    }
  }
}
```

The app now parses and stores `user.group.code`.

Changed file:

```text
lib/data/models/auth/mobile_auth_session.dart
```

### Dealer Menu Visibility

The app now exposes:

```dart
auth.canAccessDealers
```

Current rule:

```text
group.code == "so" => Dealer hidden
other roles => Dealer visible
```

There is also a fallback for old saved sessions:

```text
role == "so" or "sales officer" => Dealer hidden
```

Changed file:

```text
lib/features/auth/auth_provider.dart
```

### UI Changes

Dealer is hidden from:

- Bottom navigation.
- Dashboard module card.

Changed files:

```text
lib/app/navigation/app_shell.dart
lib/features/dashboard/screens/dashboard_tab.dart
```

The internal stack indexes were kept stable to avoid a broad navigation refactor.

## Current API Response Limitation

The login API response does not yet expose effective access rights or effective rules.

Currently exposed:

```json
{
  "role": "Sales Officer",
  "group": {
    "id": 1,
    "code": "so",
    "name": "Sales Officer"
  }
}
```

Not currently exposed:

```json
{
  "effective_access": [],
  "effective_rules": [],
  "features": {}
}
```

Recommended future contract for the app:

```json
{
  "features": {
    "dealers": {
      "visible": false,
      "read": false,
      "create": false,
      "write": false,
      "delete": false
    },
    "outlets": {
      "visible": true,
      "read": true,
      "create": true,
      "write": true,
      "delete": false
    }
  }
}
```

The app should eventually depend on feature flags, not raw `ir.rule` domains.

## Configuration Mechanism

### SO Configuration

Mobile group:

```text
Name: Sales Officer
Code: so
```

Model Access:

```text
Name: res_partner_so_outlet
Model: Contact
Read: Yes
Create: Yes
Write: Yes
Delete: No
```

Record Rule:

```text
Name: res_partner_so_outlet
Model: Contact
Domain: [('customer_type', '=', 'outlet')]
Read: Yes
Create: Yes
Write: Yes
Delete: No
Active: Yes
```

Result:

- SO can read/create/update outlets.
- SO cannot access distributor/dealer list.
- SO does not see Dealer menu in app.

### TSM Configuration

Mobile group:

```text
Name: Territory Sales Manager
Code: tsm
Implied Groups: Sales Officer
```

Do not duplicate SO outlet access on TSM unless needed. TSM inherits it through `Implied Groups`.

Add only the extra distributor/dealer rule:

Model Access:

```text
Name: res_partner_tsm_distributor
Model: Contact
Read: Yes
Create: Yes
Write: Yes
Delete: No
```

Record Rule:

```text
Name: res_partner_tsm_distributor
Model: Contact
Domain: [('customer_type', '=', 'distributor')]
Read: Yes
Create: Yes
Write: Yes
Delete: No
Active: Yes
```

Result:

- TSM inherits SO outlet access.
- TSM also gets distributor/dealer access.
- TSM sees Dealer menu in app.

### How To Verify Configuration

For SO:

1. Open `Mobile API > Configuration > User Groups`.
2. Open `Sales Officer`.
3. Confirm `Model Access` has Contact access.
4. Confirm `Record Rules` has outlet-only domain.
5. Confirm no distributor rule exists for SO.
6. Login to the app as SO.
7. Dealer should be hidden.
8. Distributor list API should be blocked.

For TSM:

1. Open `Territory Sales Manager`.
2. Confirm `Implied Groups` includes `Sales Officer`.
3. Confirm `Effective Access` shows inherited SO Contact access.
4. Confirm `Effective Rules` shows inherited SO outlet rule.
5. Add TSM distributor rule.
6. Login to the app as TSM.
7. Dealer should be visible.
8. Distributor list API should work.

## Verification Already Run

Backend:

```text
python3 -m compileall -q meta_api_user meta_ss_rest_api meta_ss_contact
python3 -m xml.etree.ElementTree meta_api_user/views/mobile_role_views.xml
git diff --check
```

Flutter edited files:

```text
dart format lib/app/navigation/app_shell.dart lib/features/dashboard/screens/dashboard_tab.dart lib/features/auth/auth_provider.dart lib/data/models/auth/mobile_auth_session.dart
dart analyze lib/app/navigation/app_shell.dart lib/features/dashboard/screens/dashboard_tab.dart lib/features/auth/auth_provider.dart lib/data/models/auth/mobile_auth_session.dart
```

Focused Flutter analysis passed with no issues.

Full Flutter `dart analyze` still reports unrelated existing warnings in inventory, sales, and routes files.

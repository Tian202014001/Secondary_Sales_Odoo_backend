# Firebase Push Notification Plan for Odoo + Flutter Secondary Sales App

## Goal

When a sale order is created from the Flutter app and later approved or
confirmed from Odoo Web, only the employee who created that sale order should
receive a mobile push notification.

Firebase is used only as the mobile push delivery transport. Odoo remains the
source of truth for users, authentication, sale orders, approval rules, stock,
business logic, notification targeting, and audit history.

------------------------------------------------------------------------

## Recommended Architecture

```text
Flutter App
   |
   | User logs in through Odoo
   |
   v
Get Firebase FCM token
   |
   | Register device token in Odoo
   |
   v
Odoo stores device token against `res.mobile.user`

Flutter App creates sale order
   |
   v
Odoo stores the real mobile creator on sale.order

Manager confirms sale order from Odoo Web
   |
   v
Odoo creates a pending mobile push notification record
   |
   v
Queue job / cron sends notification through Firebase FCM HTTP v1
   |
   v
Mobile user receives notification on all active devices
```

## Key Design Decision

Do not send the push notification directly and synchronously inside
`sale.order.action_confirm()`.

Instead:

1. Confirm the sale order normally.
2. Create a notification record in Odoo.
3. Let a queue job or cron send the notification through Firebase.
4. Log success, failure, retry count, and invalid token cleanup separately.

This prevents sale order confirmation from becoming slow or failing because of
Firebase network issues, expired tokens, or temporary FCM downtime.

------------------------------------------------------------------------

## Firebase Scope

Firebase will only manage:

- Mobile push notification delivery
- FCM device tokens
- Delivery response from FCM

Firebase will not manage:

- Users
- Authentication
- Orders
- Stock
- Approval rules
- Business logic
- Database records
- Notification targeting decisions

These remain in Odoo.

## Odoo Enterprise vs Community

The Firebase/Web Push settings in Odoo Enterprise are intended mainly for:

- Website visitor notifications
- Marketing campaigns
- Abandoned cart notifications
- Browser push notifications

For a Flutter mobile app, use a custom Firebase integration. This works in:

- Odoo Community
- Odoo Enterprise
- Odoo.sh
- Self-hosted Odoo

Do not depend on Odoo Enterprise Website Push Notifications for this mobile app
use case.

------------------------------------------------------------------------

## Firebase Setup

1. Create Firebase project: `Secondary Sales`
2. Register Android app
3. Download `google-services.json`
4. Place it in the Flutter project:

```text
android/app/google-services.json
```

5. Enable Firebase Cloud Messaging API HTTP v1.
6. Generate a Firebase service account key.
7. Store the service account JSON securely on the Odoo server.

Important:

- Do not commit the Firebase service account JSON to git.
- Prefer storing the file outside the custom module directory.
- Store only the secure file path or encrypted configuration value in Odoo.
- Use FCM HTTP v1, not legacy Firebase APIs.

------------------------------------------------------------------------

## Flutter Setup

Install packages:

```bash
flutter pub add firebase_core firebase_messaging
flutter pub get
```

Initialize Firebase:

```dart
await Firebase.initializeApp();
final token = await FirebaseMessaging.instance.getToken();
```

After successful Odoo login, send the FCM token to Odoo.

Flutter should also handle token refresh:

```dart
FirebaseMessaging.instance.onTokenRefresh.listen((token) {
  // Send updated token to Odoo.
});
```

The Flutter app should send:

- FCM token
- Platform: `android` or `ios`
- Device identifier if available
- App version
- Device name/model if available

The Flutter app should include payload handling so tapping a notification can
open the related sale order screen.

Example payload:

```json
{
  "type": "sale_order_confirmed",
  "model": "sale.order",
  "id": 123
}
```

### App-Side Implementation

After mobile login succeeds, the Flutter app must register the device token with
Odoo.

Required request:

```text
POST /api/v1/mobile/device/register
Authorization: Bearer <mobile_access_token>
Content-Type: application/json
```

Request body:

```json
{
  "fcm_token": "firebase-token",
  "platform": "android",
  "device_name": "Samsung Galaxy",
  "app_version": "1.0.0"
}
```

Recommended Flutter flow:

```dart
Future<void> registerPushDevice(String accessToken) async {
  await Firebase.initializeApp();

  final messaging = FirebaseMessaging.instance;
  await messaging.requestPermission();

  final token = await messaging.getToken();
  if (token == null || token.isEmpty) {
    return;
  }

  await odooApi.post(
    '/api/v1/mobile/device/register',
    bearerToken: accessToken,
    body: {
      'fcm_token': token,
      'platform': 'android',
      'device_name': deviceName,
      'app_version': appVersion,
    },
  );
}
```

Token refresh must also update Odoo:

```dart
FirebaseMessaging.instance.onTokenRefresh.listen((token) async {
  await odooApi.post(
    '/api/v1/mobile/device/register',
    bearerToken: accessToken,
    body: {
      'fcm_token': token,
      'platform': 'android',
      'device_name': deviceName,
      'app_version': appVersion,
    },
  );
});
```

On logout, the app should deactivate the token in Odoo:

```text
POST /api/v1/mobile/device/unregister
Authorization: Bearer <mobile_access_token>
Content-Type: application/json
```

Request body:

```json
{
  "fcm_token": "firebase-token"
}
```

Notification tap handling should read the data payload and open the sale order
detail page:

```dart
FirebaseMessaging.onMessageOpenedApp.listen((message) {
  final data = message.data;
  if (data['type'] == 'sale_order_confirmed' &&
      data['model'] == 'sale.order' &&
      data['id'] != null) {
    openSaleOrderDetail(int.parse(data['id'].toString()));
  }
});
```

Also check the initial notification when the app is launched from a terminated
state:

```dart
final initialMessage = await FirebaseMessaging.instance.getInitialMessage();
if (initialMessage != null) {
  // Handle the same sale_order_confirmed payload.
}
```

Important app-side rules:

- Register the FCM token only after Odoo mobile login succeeds.
- Always send the Odoo mobile bearer token with the register/unregister calls.
- Re-register the token when Firebase refreshes it.
- Do not send `mobile_user_id` from Flutter; Odoo derives it from the bearer
  token.
- Do not block login if token registration fails; log the error and retry later.
- Do not store Firebase service account data in the Flutter app.

------------------------------------------------------------------------

## Mobile User Model

The Flutter app uses `res.mobile.user` as the mobile app user model. This model
is the notification target and should own the mobile device tokens.

Recommended:

```text
res.mobile.user
   |
   v
mobile.device
```

If mobile users also need to be connected to Odoo employees or internal users,
add optional links from `res.mobile.user`:

```text
res.mobile.user
   | optional
   +-- hr.employee
   | optional
   +-- res.users
```

Do not use `res.users` as the mobile notification target unless the app later
changes its identity model.

### Recommended Device Model

Create:

```text
mobile.device
```

Suggested fields:

```python
mobile_user_id = fields.Many2one(
    'res.mobile.user',
    required=True,
    ondelete='cascade',
)
employee_id = fields.Many2one('hr.employee')
fcm_token = fields.Char(required=True, index=True)
platform = fields.Selection([
    ('android', 'Android'),
    ('ios', 'iOS'),
], required=True)
device_name = fields.Char()
app_version = fields.Char()
active = fields.Boolean(default=True)
last_seen_at = fields.Datetime()
```

Recommended constraints:

- FCM token should be unique.
- A mobile user can have multiple active devices.
- Old or invalid tokens should be deactivated, not hard-deleted.

------------------------------------------------------------------------

## Sale Order Integration

Because the Flutter app uses `res.mobile.user`, every sale order created from
the app should explicitly store the real mobile creator. Do not rely on Odoo's
built-in `create_uid`, because that may represent an API user, portal user, or
technical integration user instead of the real mobile employee.

Recommended field:

```python
mobile_user_id = fields.Many2one(
    'res.mobile.user',
    string='Mobile User',
    index=True,
    copy=False,
)
```

Optional employee field:

```python
mobile_employee_id = fields.Many2one(
    'hr.employee',
    string='Mobile Employee',
    index=True,
    copy=False,
)
```

When the Flutter app creates a sale order:

```text
sale.order.mobile_user_id = logged_in_res_mobile_user
```

------------------------------------------------------------------------

## Notification Model

Create:

```text
mobile.push.notification
```

Suggested fields:

```python
mobile_user_id = fields.Many2one('res.mobile.user', required=True, index=True)
sale_order_id = fields.Many2one('sale.order', index=True)
title = fields.Char(required=True)
body = fields.Text(required=True)
payload_json = fields.Text()
state = fields.Selection([
    ('pending', 'Pending'),
    ('sent', 'Sent'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
], default='pending', index=True)
provider_message_id = fields.Char()
error_message = fields.Text()
retry_count = fields.Integer(default=0)
sent_at = fields.Datetime()
```

Recommended constraints:

- Prevent duplicate sale order confirmation notifications for the same mobile
  user.
- Keep notification history for audit and support.
- Store Firebase response IDs when available.

------------------------------------------------------------------------

## Notification Service

Create:

```text
mobile.notification.service
```

Responsibilities:

- Create notification records
- Send notification to one mobile user
- Send notification to multiple mobile users when needed
- Send to all active devices of a mobile user
- Communicate with Firebase FCM HTTP v1
- Retry temporary failures
- Mark permanent failures
- Deactivate invalid or expired FCM tokens
- Log notification history

The service should send to all active devices for the target `res.mobile.user`.
This covers employees who use the app on multiple phones or tablets.

------------------------------------------------------------------------

## Sale Order Confirmation Flow

```text
Mobile User Creates Sale Order
        |
        v
sale.order.mobile_user_id is set
        |
        v
Manager confirms sale order from Odoo Web
        |
        v
sale.order.action_confirm()
        |
        v
Odoo creates pending mobile.push.notification
        |
        v
Queue job / cron sends notification
        |
        v
Firebase FCM
        |
        v
Only the creator receives the notification
```

Recommended trigger behavior:

- Send only when the order first enters the confirmed/sale state.
- Do not resend when `action_confirm()` is called again on an already confirmed
  order.
- Do not send if there is no mobile creator.
- Do not send if the creator has no active FCM devices.
- Do not block sale order confirmation if notification creation or delivery
  fails.

Example notification content:

```text
Title: Sale Order Confirmed
Body: Your sale order SO123 has been confirmed.
```

Example payload:

```json
{
  "type": "sale_order_confirmed",
  "model": "sale.order",
  "id": 123,
  "name": "SO123"
}
```

------------------------------------------------------------------------

## API Endpoints

Create an authenticated Odoo controller endpoint for device registration.

Example:

```text
POST /mobile/device/register
```

Request body:

```json
{
  "fcm_token": "firebase-token",
  "platform": "android",
  "device_name": "Samsung Galaxy",
  "app_version": "1.0.0"
}
```

Behavior:

- Authenticate the request using the logged-in `res.mobile.user`.
- Create or update the `mobile.device` record.
- If the same token exists for another mobile user, reassign it to the current
  mobile user or deactivate the old record based on the app's login policy.
- Update `last_seen_at`.

Also create an optional logout endpoint:

```text
POST /mobile/device/unregister
```

This can deactivate the token on logout.

------------------------------------------------------------------------

## Queue / Cron Strategy

Preferred option:

- Use `queue_job` if the project already uses OCA queue infrastructure.

Simple option:

- Use an Odoo scheduled action/cron that processes pending notification records.

Cron behavior:

```text
Find pending or retryable failed notifications
   |
   v
Send through Firebase
   |
   v
Mark sent or failed
   |
   v
Deactivate invalid tokens when FCM reports permanent token errors
```

Suggested retry policy:

- Retry temporary network/server failures.
- Do not retry permanent invalid token failures.
- Keep a maximum retry count, for example 3 or 5.

------------------------------------------------------------------------

## Testing Plan

### Phase 1: Flutter Token

- Initialize Firebase in Flutter.
- Generate FCM token.
- Confirm token refresh handling works.

### Phase 2: Direct FCM Test

- Send a direct notification to one FCM token using Firebase HTTP v1.
- Confirm notification appears on the Android device.

### Phase 3: Odoo Device Registration

- Add `/mobile/device/register`.
- Login from Flutter.
- Send FCM token to Odoo.
- Confirm `mobile.device` record is created or updated.

### Phase 4: Odoo Test Button

- Add a temporary test action in Odoo to create a notification for the current
  mobile user.
- Process it through the notification service.
- Confirm the notification reaches the mobile device.

### Phase 5: Sale Order Trigger

- Create a sale order from Flutter.
- Confirm `mobile_user_id` is set.
- Confirm the sale order from Odoo Web.
- Confirm one pending notification record is created.
- Confirm the notification is sent to only the creator's active devices.

### Phase 6: Failure Cases

- Test expired or invalid FCM token handling.
- Test mobile user with multiple devices.
- Test mobile user with no active devices.
- Test confirming the same order more than once.
- Test Firebase downtime or network failure.

------------------------------------------------------------------------

## Final Recommendation

Use:

```text
Flutter Firebase Messaging
+
Odoo authenticated device registration
+
Device tokens linked to res.mobile.user
+
Sale order `mobile_user_id` creator tracking
+
Durable mobile.push.notification records
+
Async queue job or cron delivery
+
Firebase FCM HTTP v1 sender
+
Retry, logging, and invalid-token cleanup
```

Firebase is the right delivery tool for Flutter push notifications. The
important production improvement is to make Odoo's notification layer durable,
asynchronous, auditable, and tied cleanly to the real `res.mobile.user` who
created the sale order.

------------------------------------------------------------------------

## End-to-End Setup and Deployment Runbook

This section documents the full manual setup from Firebase project creation to
Odoo server deployment and APK testing.

### 1. Firebase Project Creation

1. Open Firebase Console:

```text
https://console.firebase.google.com/
```

2. Click **Add project**.
3. Project name:

```text
Secondary Sales
```

4. Google Analytics is optional for this push notification use case.
5. Create the project.

Firebase is used only for push notification delivery. Do not configure Firebase
Authentication, Firestore, Realtime Database, or business data storage for this
use case.

### 2. Register Android App in Firebase

1. Open the Firebase project.
2. Click **Add app**.
3. Select **Android**.
4. Enter the Android package name from the Flutter app.

Check the package name in:

```text
android/app/build.gradle.kts
```

Look for:

```text
applicationId
```

5. Optional app nickname:

```text
Secondary Sales Android
```

6. Register the app.
7. Download:

```text
google-services.json
```

8. Place it in the Flutter app:

```text
/home/abrar/AndroidStudioProjects/secondary_sales/android/app/google-services.json
```

This file belongs to the Flutter app. It is not the Firebase service account
private key.

### 3. Enable Firebase Cloud Messaging

1. In Firebase Console, open:

```text
Project settings > Cloud Messaging
```

2. Confirm Firebase Cloud Messaging API / HTTP v1 API is enabled.
3. Note the Firebase project ID. It is useful for debugging FCM responses.

The backend uses the Firebase Admin SDK, which authorizes server-side sends
using a trusted service account.

### 4. Generate Firebase Service Account JSON

1. In Firebase Console, open:

```text
Project settings > Service accounts
```

2. Click **Generate new private key**.
3. Download the JSON key file.
4. Rename it locally to something clear:

```text
firebase-secondary-sales-service-account.json
```

Important security rules:

- Do not commit this JSON file to git.
- Do not put this JSON file inside the Flutter app.
- Do not include this JSON file inside the APK.
- Store it only on the trusted Odoo server.
- Restrict file permissions on self-hosted servers.

### 5. Flutter App Configuration

The Flutter app must have these packages:

```yaml
firebase_core: ^3.1.0
firebase_messaging: ^15.0.0
```

The current app already includes them in:

```text
/home/abrar/AndroidStudioProjects/secondary_sales/pubspec.yaml
```

The app also has:

```text
android/app/google-services.json
```

Android permission required for Android 13+:

```xml
<uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
```

The current app registers the FCM token after Odoo mobile login by calling:

```text
POST /api/v1/mobile/device/register
Authorization: Bearer <mobile_access_token>
```

The app unregisters the device token on logout:

```text
POST /api/v1/mobile/device/unregister
Authorization: Bearer <mobile_access_token>
```

The app should never send `mobile_user_id`. Odoo derives the mobile user from
the bearer token.

### 6. Odoo Backend Code Deployment

Deploy these backend parts:

```text
meta_firebase_push_notification
meta_ss_rest_api changes for mobile_api_user_id context
```

Required backend behavior:

- `res.mobile.device` stores FCM tokens against `res.mobile.user`.
- `/api/v1/mobile/device/register` creates or updates the device token.
- `/api/v1/mobile/device/unregister` deactivates the token.
- `sale.order.mobile_user_id` is set from the authenticated mobile user.
- `action_confirm()` creates one pending `mobile.push.notification`.
- cron processes pending notifications asynchronously.

### 7. Python Dependency Configuration

The backend imports:

```python
firebase_admin
```

Add this to the Odoo deployment `requirements.txt`:

```text
firebase-admin
```

Recommended after testing:

```text
firebase-admin==<tested-version>
```

For Odoo.sh, put `requirements.txt` in the branch root or the parent folder that
contains custom Odoo modules. Odoo.sh installs additional Python dependencies
from `requirements.txt` during container builds.

After deployment, check:

```text
/home/odoo/logs/pip.log
```

or the Odoo.sh build logs to confirm `firebase-admin` installed successfully.

### 8. Service Account Storage on Server

#### Self-hosted Odoo

Recommended path:

```text
/opt/odoo/secrets/firebase-service-account.json
```

Example permissions:

```bash
sudo mkdir -p /opt/odoo/secrets
sudo chown odoo:odoo /opt/odoo/secrets/firebase-service-account.json
sudo chmod 600 /opt/odoo/secrets/firebase-service-account.json
```

Then set Odoo system parameter:

```text
firebase.service_account_path = /opt/odoo/secrets/firebase-service-account.json
```

Restart Odoo after setting the file and dependency.

#### Odoo.sh

Do not commit the service account JSON into the repository.

Current backend code reads a file path from:

```text
firebase.service_account_path
```

For Odoo.sh, the practical options are:

1. Upload the JSON file through Odoo.sh shell to a private path and set that path
   in `firebase.service_account_path`.
2. Verify the file still exists after rebuild/redeploy.
3. If the file path is not stable on your Odoo.sh setup, change the backend to
   read service account JSON content from a private Odoo system parameter or
   protected attachment instead of a filesystem path.

Suggested Odoo.sh private path to test:

```text
/home/odoo/data/firebase-service-account.json
```

Then set:

```text
firebase.service_account_path = /home/odoo/data/firebase-service-account.json
```

Verify from Odoo.sh shell:

```bash
python3 -c "import firebase_admin; print('firebase_admin ok')"
ls -l /home/odoo/data/firebase-service-account.json
```

If the file disappears after rebuild, do not continue with file-path storage.
Use system-parameter JSON content or a protected attachment approach.

### 9. Odoo System Parameter

Enable developer mode in Odoo, then go to:

```text
Settings > Technical > Parameters > System Parameters
```

Create:

```text
Key: firebase.service_account_path
Value: /path/to/firebase-service-account.json
```

Examples:

Self-hosted:

```text
/opt/odoo/secrets/firebase-service-account.json
```

Odoo.sh test path:

```text
/home/odoo/data/firebase-service-account.json
```

### 10. Upgrade Odoo Module

After pushing backend code:

1. Update app list.
2. Upgrade:

```text
meta_firebase_push_notification
```

3. Confirm these models exist:

```text
res.mobile.device
mobile.push.notification
mobile.notification.service
```

4. Confirm cron exists and is active:

```text
Process Mobile Push Notifications
```

5. Confirm `sale.order` has:

```text
mobile_user_id
```

Important upgrade note:

The notification model has a uniqueness constraint. If there are already
duplicate rows for the same sale order, mobile user, and notification type,
clean duplicates before upgrading.

### 11. Backend Smoke Test

Login from Flutter or Postman and get a mobile bearer token.

Call:

```text
POST /api/v1/mobile/device/register
Authorization: Bearer <mobile_access_token>
Content-Type: application/json
```

JSON-RPC body:

```json
{
  "jsonrpc": "2.0",
  "method": "call",
  "params": {
    "fcm_token": "test-device-token",
    "platform": "android",
    "device_name": "Manual Test",
    "app_version": "1.0.0"
  },
  "id": 1
}
```

Expected response:

```json
{
  "success": true,
  "message": "Device registered successfully."
}
```

Then verify in Odoo:

```text
res.mobile.device
```

Expected:

- `mobile_user_id` is the logged-in mobile user.
- `fcm_token` is stored.
- `active` is true.
- `last_seen_at` is set.

### 12. Build APK

From Flutter app directory:

```bash
cd /home/abrar/AndroidStudioProjects/secondary_sales
flutter clean
flutter pub get
flutter build apk --release
```

APK output:

```text
build/app/outputs/flutter-apk/app-release.apk
```

Install on Android device:

```bash
adb install -r build/app/outputs/flutter-apk/app-release.apk
```

The Android device must have Google Play services available.

### 13. Manual End-to-End Test

1. Install the APK.
2. Open the app.
3. Configure Odoo server URL and database.
4. Login as a mobile user.
5. Accept notification permission.
6. In Odoo, verify a `res.mobile.device` record was created.
7. Create a sale order from the app.
8. In Odoo, verify the sale order has:

```text
mobile_user_id = logged-in res.mobile.user
```

9. Confirm the sale order from Odoo Web.
10. Verify one pending notification was created:

```text
mobile.push.notification
state = pending
notification_type = sale_order_confirmed
mobile_user_id = creator
sale_order_id = confirmed order
```

11. Wait for cron or manually run:

```text
Process Mobile Push Notifications
```

12. Expected result:

- notification state becomes `sent`;
- phone receives push notification;
- tapping the notification opens the sale order detail page.

### 14. Failure Test Cases

Test these before production rollout:

- Login creates/updates one active `res.mobile.device`.
- Token refresh updates the same token record or creates a new valid record.
- Logout deactivates the token.
- User with no active device does not break sale order confirmation.
- Expired/invalid FCM token is deactivated by the cron sender.
- Confirming the same sale order twice does not create duplicate notifications.
- Firebase outage does not block sale order confirmation.
- App launched from terminated state opens sale order detail when notification is
  tapped.

### 15. Troubleshooting

#### `firebase-admin python package is not installed`

Cause:

```text
firebase-admin
```

is missing from `requirements.txt` or failed during build.

Fix:

- Add `firebase-admin` to `requirements.txt`.
- Rebuild/redeploy.
- Check Odoo.sh `pip.log` or server install logs.

#### `firebase.service_account_path is not set`

Cause:

Odoo system parameter is missing.

Fix:

Create:

```text
firebase.service_account_path = /path/to/firebase-service-account.json
```

#### Firebase credential file not found

Cause:

The path in `firebase.service_account_path` does not exist from the Odoo server
process.

Fix:

- Check the path.
- Check permissions.
- On Odoo.sh, verify the file still exists after rebuild.

#### Flutter login works but no `res.mobile.device`

Check:

- Android notification permission was accepted.
- Device has Google Play services.
- `android/app/google-services.json` exists.
- Flutter app is calling `/api/v1/mobile/device/register`.
- Odoo mobile bearer token is valid.
- Odoo server logs for validation errors.

#### Notification record is pending but no push arrives

Check:

- cron is active;
- `firebase-admin` is installed;
- service account path is configured;
- service account JSON is valid;
- FCM token is active;
- Odoo log contains Firebase errors.

### 16. Source References

- Firebase Flutter setup:
  `https://firebase.google.com/docs/flutter/setup`
- Firebase FCM HTTP v1 authorization:
  `https://firebase.google.com/docs/cloud-messaging/send/v1-api#authorize-http-v1-send-requests`
- Odoo.sh container and `requirements.txt` dependency behavior:
  `https://www.odoo.com/documentation/18.0/administration/odoo_sh/advanced/containers.html`

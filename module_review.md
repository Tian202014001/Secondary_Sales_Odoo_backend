# Secondary Sales Backend — Module Review (Updated - Post Fixes)

This document contains a comprehensive review and rating of all eight Odoo 18 backend modules under `/home/abrar/odoo/odoo_18/custom/test_user`. These modules form the backend services for the secondary sales mobile application.

## Module Inventory & Ratings

| Module | Purpose | Key Files | Rating |
| :--- | :--- | :--- | :---: |
| **`meta_api_user`** | JWT auth, mobile users, sessions, roles, and RBAC infrastructure | `res_mobile_user.py`, `mobile_role.py`, `mobile_auth_session.py`, `mobile_auth_controller.py` | ⭐⭐⭐⭐½ |
| **`meta_firebase_push_notification`** | FCM device token registration, device tracking, and transactional push notifications | `mobile_device.py`, `mobile_push_notification.py`, `mobile_notification_service.py`, `sale_order.py` | ⭐⭐⭐⭐½ |
| **`meta_ss_sales`** | Sales orders, deliveries, auto-invoicing, and PDF generation | `sale_order.py`, `stock_picking.py`, `sales.py`, `sale_order_details.py` | ⭐⭐⭐⭐½ |
| **`meta_ss_transfer`** | Van loading/unloading (virtual transfers), returns, and scraps | `transfer_common.py`, `virtual_transfers.py`, `returns.py`, `scraps.py` | ⭐⭐⭐⭐½ |
| **`meta_ss_rest_api`** | Shared API utilities, configuration parameters, products, warehouses, and locations | `common.py`, `helpers.py`, `mobile_policy.py`, `products.py`, `locations.py` | ⭐⭐⭐⭐ |
| **`meta_ss_contact`** | `res.partner` extensions (customer types), and automated customer stock location hierarchy | `res_partner.py`, `contacts.py` (controllers/utils) | ⭐⭐⭐⭐ |
| **`meta_ss_employee`** | Employee CRUD API and subordinate hierarchy management | `employees.py` (controllers/utils) | ⭐⭐⭐⭐ |
| **`meta_ss_route_management`** | Route planning, daily routes, outlet visits, and joint visit tracking | `route_management.py`, `outlet_visit.py`, `routes.py` (controllers/utils) | ⭐⭐⭐⭐ |

**Overall Rating: 8.5 / 10** (Excellent structure; recent cleanup of transfers, wiring of RBAC in key modules, and fixes of joint visit performance, manifest structures, and correct computed field fallback behavior show great software engineering maturity).

---

## Architecture Review

### What's Done Well ✅

1. **Clean Layer Separation** — Every module strictly follows the `controllers/ → utils/ → models/` pattern. Business logic resides in `utils/` or the models themselves, keeping the controllers thin and focused. This pattern makes the codebase highly testable and readable.
2. **Consolidated Transfer Engine** — The reorganization of scraps and returns logic into a shared `transfer_common.py` module using `TransferFlavor` parameterization is a brilliant design decision. It eliminates hundreds of lines of duplicate code, centralizes lot validation/allocations, and makes adding new types of transfers trivial.
3. **Robust Auth Foundation** — `meta_api_user` implements a production-grade auth flow: bcrypt password hashing (with 72-byte truncation safety), JWT access tokens (15-min TTL), SHA-256 hashed refresh tokens (30-day TTL), and device-level session invalidation. The admin OWL dashboard is a great touch for visibility.
4. **FCM Push Notification Integration** — The `meta_firebase_push_notification` module is beautifully designed. It registers client tokens, tracks active devices per user, logs message delivery states, automatically deactivates stale tokens on permanent error (e.g., `UNREGISTERED` or `INVALID_ARGUMENT`), and queues notifications to be sent asynchronously via a cron job to avoid blocking API threads.
5. **Partial RBAC Wiring** — The model access control (`check_mobile_model_access`) and record-level rule filtering (`apply_mobile_rule_domain`) have been successfully integrated into `meta_ss_sales` and `meta_ss_contact`. This closes security loops in key transaction endpoints.
6. **Optimized Joint Visit Linking** — The `_link_visits()` method in `outlet_visit.py` has been optimized. By adding day-level constraints to the candidate search domain (`'check_in_time', '>=', date_start` and `'check_in_time', '<=', date_end`), we restrict search records to only those created on the same day. This removes the $O(n^2)$ lookup scale problem.
7. **Idempotent Operations** — Critical for mobile clients on poor connections. Invoicing, scrap generation, and location provisions check search histories before creating duplicates.
8. **Standardized Error Handling** — The return and scrap controllers now properly map validation exceptions to `"validation_error"` and general exceptions to `"server_error"`, matching Odoo API standard formats.

### Issues & Improvement Areas ⚠️

1. **Gaps in RBAC Enforcement** — Although `meta_ss_sales` and `meta_ss_contact` are secured, the other business modules—specifically **`meta_ss_employee`**, **`meta_ss_route_management`**, and **`meta_ss_transfer`**—do not perform any role-based validation. Any authenticated mobile user can call these APIs.
2. **Pervasive `.sudo()` Usage** — All controllers call `get_mobile_api_context()`, which fetches a `.sudo()` integration environment. While necessary under a single integration user pattern, it places the entire burden of security verification on custom Python policy checks (which are not yet fully implemented across all modules).
3. **Refactoring & Configs** — 
   - The environment configuration (`config.py`) hardcodes the server URL and DB name, which should instead be managed through `ir.config_parameter`.
   - The route controller `routes.py` (821 lines) handles too many unrelated responsibilities (route CRUD, outlet additions, visit check-in/out, and link tracking). It should be split into distinct controllers.

---

## Opinion 1: Role-Based Authorization Strategy

### Current State
You already have a highly capable RBAC engine built in `meta_api_user/models/mobile_role.py` and wrapped by `meta_ss_rest_api/utils/mobile_policy.py`:
- `res.mobile.user.group` holds model access controls and record rules.
- `MobilePolicy` checks model-level permissions and evaluates record rules inside a custom evaluation context (injecting `mobile_user`, `employee`, and `company_id`).

### Recommendation
Extend the security middleware to all controllers:
1. **Model Access Checks**: Call `check_mobile_model_access(mobile_user, "model.name", "operation")` at the beginning of each endpoint in `meta_ss_employee`, `meta_ss_route_management`, and `meta_ss_transfer`.
2. **Row-Level Domain Filters**: Apply the rule domain dynamically when querying lists or performing bulk actions. For example, in `meta_ss_route_management`:
   ```python
   domain = [('employee_id', '=', employee.id)]
   domain = apply_mobile_rule_domain(mobile_user, "sale.route", "read", domain)
   routes = api_env["sale.route"].search(domain)
   ```
3. **App-Side Gating**: Return `group.get_mobile_access_summary()` in the authentication response (during login/refresh). The Flutter app can use this dictionary to dynamically show or hide UI components (like the 'Create Route' or 'Manage Transfers' menus).

---

## Opinion 2: Offline-First Strategy for Flutter App

### Why Offline-First?
Field sales agents work in remote environments with inconsistent network coverage. Forcing them to wait on synchronous network requests for basic tasks (like checking into a visit, searching the catalog, or drafting an order) degrades UX and halts operations when offline.

### Design Pattern
1. **Local SQLite Database**: Use `drift` or `sqflite` to store read-only master data (products, pricing, outlet list, daily routes) and queue write operations.
2. **Local Write Sync Queue**: Instead of sending POST requests directly to endpoints, write drafts (orders, visits) to a local `sync_queue` table.
3. **Batch Sync API**: Implement a consolidated endpoint `/api/v1/sync` in Odoo:
   - Accept a list of operations (with client UUIDs to prevent double-processing).
   - Process them within a transaction and return status mappings.
   - Return any master records updated since the client's last sync timestamp.

---

## Prioritized Recommendations

### Priority 1: Security & Performance

- [ ] **Wire RBAC to Remaining Modules**: Add `check_mobile_model_access` and `apply_mobile_rule_domain` to employee, route management, and transfer APIs.
- [ ] **Decouple Configurations**: Replace hardcoded values in `config.py` with Odoo system parameters (`ir.config_parameter`).
- [ ] **Refactor Route Controller**: Split `routes.py` (821 lines) into two controllers: `routes.py` (handling route CRUD) and `visits.py` (handling visit check-in/out and joint link tracking).

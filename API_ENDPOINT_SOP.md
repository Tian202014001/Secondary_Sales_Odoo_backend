# Mobile API Endpoint SOP (Secondary Sales backend)

Standard operating procedure for building JSON‑RPC endpoints consumed by the Flutter app.
Follow this for **every** new endpoint. It exists because the mobile app talks to Odoo through a
**single, locked‑down integration user**, and getting the access / context / error handling wrong
causes the recurring "doesn't have access" and "impersonation" bugs.

---

## 1. Architecture in one paragraph

Every request is authenticated by a **Bearer JWT** (mobile session), but all ORM work runs through
one Odoo **integration user** (`ir.config_parameter` `meta_api_user.integration_user_id`).
`get_mobile_api_context()` validates the token and returns an env whose context carries
`mobile_api_user_id` and whose `employee_id` in the payload is the **token‑trusted** one.
Because the integration user must NOT be trusted with native ACLs, **all ORM calls use `.sudo()`**,
and authorization is enforced explicitly in code (via `MobilePolicy` / manager checks), never by
relying on the integration user's groups.

Key helpers (all in `meta_ss_rest_api/utils/common.py` unless noted):
- `get_mobile_api_context(payload, require_employee=False)` → `(mobile_user, api_env, payload)`
- `handle_api_exception(exc, message=None)` → safe error envelope
- `error_response(code, message, data=None)`
- `check_mobile_model_access(mobile_user, model, op)` / `apply_mobile_rule_domain(...)` / `mobile_rule_domain_allows_values(...)`
- `get_pagination(payload)` (routes utils) / `get_sales_pagination(payload)`

---

## 2. The canonical endpoint template — copy this

```python
from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX, API_VERSION, error_response, get_mobile_api_context,
    handle_api_exception, check_mobile_model_access, apply_mobile_rule_domain,
)


class MyController(http.Controller):

    @http.route(f"{API_PREFIX}/my/thing", type="json", auth="user", methods=["POST"])
    def create_thing(self, **payload):
        try:
            # 1. AUTH + trusted context — always capture the return values.
            mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)

            # 2. AUTHORIZATION (explicit — sudo below bypasses native ACLs).
            check_mobile_model_access(mobile_user, "my.model", "create")

            # 3. VALIDATION — raise ValidationError for bad input.
            name = payload.get("name")
            if not name:
                raise ValidationError("'name' is required.")

            # 4. ORM — always .sudo(); use api_env, never request.env.
            record = api_env["my.model"].sudo().create({"name": name})

            # 5. SUCCESS envelope.
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Thing created successfully.",
                "data": {"id": record.id, "name": record.name},
            }
        except Exception as exc:
            # 6. One handler. Never leak str(exc) for unexpected errors.
            return handle_api_exception(exc)
```

---

## 3. Hard rules (do these every time)

1. **Use `api_env`, never `request.env`, for ORM.** `get_mobile_api_context` returns `api_env`
   carrying `mobile_api_user_id`. `request.env` does **not** — using it silently breaks chatter
   attribution and drops the token‑trusted `employee_id` (impersonation risk).
   → Always: `mobile_user, api_env, payload = get_mobile_api_context(payload, ...)`.

2. **`.sudo()` every ORM op** (`create/write/search/browse/read/unlink`, and `.exists()`).
   The integration user is (and must stay) locked down; a bare op raises
   `AccessError` the moment Odoo touches a restricted model — including **indirectly** via
   compute/onchange/constraint (e.g. creating `hr.leave`/`sale.order` reads `res.users`/`res.partner`).
   Reading a field off a sudo recordset inherits sudo, so sudo the *base* recordset.

3. **Never rely on the integration user's groups for access.** Do not "fix" an AccessError by adding
   groups to the integration user. Keep it minimal; use `.sudo()` + explicit authorization.
   (Granting it Administrator/Internal‑User to work around missing sudo is a security hole.)

4. **Trust the token, not the client.** Use the `employee_id` from the returned `payload`
   (already overridden with the token's employee). Never scope data by a client‑supplied id you
   didn't re‑derive from `mobile_user` / trusted payload.

5. **Authorization is explicit and separate from sudo.** Call `check_mobile_model_access(...)` and/or
   `apply_mobile_rule_domain(...)` (see `sales.py`). `.sudo()` gives you the *ability*; MobilePolicy
   decides *permission*.

6. **One error handler per endpoint:** `except Exception as exc: return handle_api_exception(exc)`.
   Do **not** write `error_response(400, str(e))` — it leaks internals. See §5.

7. **Route decorator:** `type="json"`, `auth="user"`, `methods=["POST"]`, path prefixed with
   `API_PREFIX` (`/api/v1`).

8. **Response envelope is fixed:**
   `{"success": true, "api_version": API_VERSION, "message": "...", "data": ..., "pagination": {...}}`
   for success; errors come from `error_response` / `handle_api_exception`.

---

## 4. Error handling taxonomy (matches the codebase)

`handle_api_exception(exc, message=None)` maps:
- `ValidationError` / `UserError` / `AccessError` / `AccessDenied` / `MissingError`
  → `error_response("validation_error", str(exc))` — safe, user‑facing message.
- anything else → rollback + server‑side traceback log + `error_response("server_error", generic)` —
  **no internal detail leaks to the client.**

So: `raise ValidationError("clean message")` for anything the user should see; let everything else
fall through to the generic `server_error`. Use string codes `"validation_error"` / `"server_error"`,
not numeric ones, for consistency across the API.

---

## 5. Approve / refuse (state‑transition) endpoints — special case

`sudo()` makes `env.is_admin()` return `True`, which will **bypass** any "manager‑only" policy that
guards with `if not self.env.is_admin()`. Two accepted patterns:

- **Model‑enforced** (preferred, see `meta_ss_expense`): the policy method enforces whenever
  `mobile_api_user_id` is in context, *regardless* of `is_admin`. Then the controller can safely
  `sheet.sudo().action_...()`.
- **Controller‑enforced** (see `meta_ss_leave_request`): verify the acting employee is the target's
  `parent_id` (manager) in the controller **before** calling `record.sudo().action_...()`.

Never `sudo()` a state transition without one of these guards in place.

---

## 6. Chatter attribution (free, if you follow the rules)

`meta_ss_chatter_attribution` rewrites chatter authored during an API request to
`"<integration user> (<employee>)"`. It works **only** because the record is created through
`api_env` (context has `mobile_api_user_id`) — even under `.sudo()`. If you use `request.env`, the
label is lost. This is another reason rule §3.1 is mandatory.

---

## 7. Pre‑merge checklist

- [ ] `mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=…)` — return captured.
- [ ] No `request.env["…"]` ORM ops (only `request.env.cr` for the cursor is OK).
- [ ] Every ORM op is `.sudo()` (create/write/search/browse/exists).
- [ ] Authorization enforced explicitly (`check_mobile_model_access` / manager check), not via the integration user's groups.
- [ ] Scoping uses the token‑trusted `employee_id`, not raw client input.
- [ ] Single `except Exception as exc: return handle_api_exception(exc)`; no `str(e)` leaks.
- [ ] State transitions (approve/refuse/confirm) keep the policy enforced under sudo.
- [ ] Success envelope + string error codes.
- [ ] `type="json"`, `auth="user"`, `POST`, `API_PREFIX` path.

---

## 8. Known anti‑patterns currently in the codebase (fix when touched)

Non‑`sudo()` ORM ops that currently work **only because the integration user is broadly privileged**
(see §3.3). They will break when it is locked down as this SOP recommends. **These are not all active
crashes today** — verify each against the real integration‑user config before treating as a bug.

> **Current project decision (2026‑07‑01):** keep the integration user broadly privileged and fix
> these **as‑found** (sudo an endpoint only when it actually breaks — `leave`/`expense` are done).
> New endpoints must still follow §§1–7 (sudo + `api_env`) — it is free to do right from the start.

Prioritized by how much they depend on that privilege:

**HIGH — create/write on privileged models:**
- `meta_ss_sales/controllers/sales.py:112` — `sale.order.create`. **Not a crash:** when neither the
  employee nor the customer has a linked user, `_compute_user_id` falls back to `self.env.user`
  (the integration user), so the salesperson becomes `meta_api_user` (verified by testing). Reading
  `partner.user_id` there does not force a `res.users` ACL read. Only breaks if the integration user
  loses `sale.order` create or the `group_sale_salesman` group. Sudo would change the fallback
  salesperson, so leave this one as‑is unless the user is locked down.
- `meta_ss_employee/controllers/employees.py:92` — `hr.employee.create`.
- `meta_ss_route_management/controllers/routes.py:253` (`sale.route.create`), `:377` (`sale.route.line.create`).
- `meta_ss_transfer/controllers/virtual_locations.py:83` (`stock.location.create`), `:90` (`res.partner.browse`).

**MEDIUM — reads on restricted models:**
- `meta_ss_attendance/controllers/attendance.py` — `hr.employee.browse` (93,126,191), `hr.attendance.search`/`search_count` (98,135,139).
- `meta_ss_contact/controllers/contacts.py` — `sale.order.search` (235), `outlet.visit.search` (240).
- `meta_ss_employee/utils/employees.py` — `hr.employee.browse`/`search` (53,63).
- `meta_ss_rest_api/controllers/products.py` — `hr.employee.browse` (35), `stock.quant.search` (46).
- `meta_ss_rest_api/controllers/van_loading.py` — `hr.employee.browse` (27), `sale.target.line.search` (70).
- `meta_ss_route_management/controllers/routes.py` — `hr.employee.browse().exists()` (147,246,348,472,574,642), `sale.route.search` (355), `sale.route.line.search` (367).
- `meta_ss_sales/controllers/deliveries.py` — `stock.quant.search` (128).

**LOW — inherit env from a parent recordset (safe only if the caller passed a sudo recordset; verify):**
- `meta_ss_route_management/utils/routes.py:263` — `route.env["sale.route.line"].search_count`.
- `meta_ss_transfer/utils/virtual_locations.py:61,165` — `env["stock.location"].search` / `stock_location.env[...]`.

Already compliant references to copy from: `meta_ss_transfer/utils/transfer_common.py`,
`meta_ss_contact/controllers/contacts.py` (most ops), and `meta_ss_leave_request` / `meta_ss_expense`
(fixed 2026‑07‑01).

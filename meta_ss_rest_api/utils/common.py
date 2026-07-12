# -*- coding: utf-8 -*-

import functools
import logging
from odoo.http import request
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError

from odoo.addons.meta_ss_rest_api.utils.mobile_policy import MobilePolicy

_logger = logging.getLogger(__name__)

API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"


def format_date(value):
    """Return an ISO-8601 date string from a date/datetime field, or None."""
    if not value:
        return None
    return str(value) if not hasattr(value, "isoformat") else value.isoformat()


def error_response(code, message, data=None):
    """Return a consistent JSON error payload."""
    response = {
        "success": False,
        "error": code,
        "message": message,
    }
    if data is not None:
        response["data"] = data
    return response


def handle_api_exception(exc, message=None):
    """Map an exception to a safe API error response (matches the app convention).

    Known, user-facing errors (Validation/User/Access/Missing) are surfaced with
    their own message under the ``"validation_error"`` code. Anything else is
    treated as unexpected: a full traceback is logged server-side and a generic
    ``"server_error"`` message is returned so no internal detail leaks to the
    client. The transaction is always rolled back so no partial writes persist.
    """
    try:
        request.env.cr.rollback()
    except Exception:  # pragma: no cover - rollback must never mask the original error
        pass
    if isinstance(exc, (AccessDenied, AccessError, MissingError, UserError, ValidationError)):
        return error_response("validation_error", str(exc))
    _logger.exception("Unhandled API error")
    return error_response("server_error", message or "An unexpected error occurred.")


def check_api_permission():
    """Retrieve the bearer token from headers and validate it.

    Returns:
        res.mobile.user: The authenticated mobile user record.
    """
    auth_header = request.httprequest.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AccessDenied("Authorization header with Bearer token is required.")

    token = auth_header[7:].strip()
    if not token:
        raise AccessDenied("Bearer token is empty.")

    mobile_user, _payload, _session = (
        request.env["mobile.auth.session"]
        .sudo()
        .validate_access_token(token, check_session=True)
    )
    return mobile_user


def get_mobile_api_context(payload=None, require_employee=False):
    """Validate the mobile JWT and return a trusted ORM context.

    Odoo's session selects the database and satisfies auth="user" routes. The
    bearer token remains the real mobile identity. When a mobile user is linked
    to an employee, any incoming employee_id is replaced with the trusted one
    from the token so API callers cannot impersonate another employee.
    """
    mobile_user = check_api_permission()
    if require_employee and not mobile_user.employee_id:
        raise AccessDenied("The mobile user is not linked to an employee.")

    trusted_payload = dict(payload or {})
    if mobile_user.employee_id:
        trusted_payload["employee_id"] = mobile_user.employee_id.id

    api_env = request.env["mobile.auth.session"].sudo().get_integration_env()
    api_env = api_env(context=dict(api_env.context, mobile_api_user_id=mobile_user.id))
    return mobile_user, api_env, trusted_payload


def require_ui_access(mobile_user, key):
    """Fail-closed API gate for a synced mobile UI resource key.

    Unlike ``MobilePolicy.has_ui_access`` for UI visibility, endpoint
    authorization must deny unknown or unmapped keys so a typo cannot become an
    open endpoint.
    """
    key = (key or "").strip()
    if not key:
        raise AccessDenied("Missing access resource key.")

    resource = mobile_user.env["mobile.ui.resource"].sudo().search([
        ("key", "=", key),
        ("active", "=", True),
    ], limit=1)
    if not resource:
        raise AccessDenied("Unknown access resource '%s'." % key)
    if not resource.module_ids:
        raise AccessDenied("Access resource '%s' is not assigned to a module." % key)

    group = mobile_user.sudo().group_id
    if not group:
        raise AccessDenied("The mobile user has no assigned mobile group.")
    if resource not in group.sudo().effective_resource_ids:
        raise AccessDenied("You do not have access to this operation.")
    return True


def require_any_ui_access(mobile_user, keys):
    """Allow the endpoint when any one fail-closed resource key is granted."""
    denied = []
    for key in keys or []:
        try:
            require_ui_access(mobile_user, key)
            return key
        except AccessDenied as exc:
            denied.append(str(exc))
    if denied:
        raise AccessDenied("You do not have access to this operation.")
    raise AccessDenied("Missing access resource key.")


def sale_type_from_payload(payload, default="primary"):
    sale_type = (
        (payload or {}).get("sale_type")
        or (payload or {}).get("type")
        or default
        or ""
    )
    sale_type = sale_type.strip().lower() if isinstance(sale_type, str) else ""
    if sale_type not in ("primary", "secondary"):
        raise ValidationError("Invalid sale type. Must be 'primary' or 'secondary'.")
    return sale_type


def sale_type_key(payload, primary_key, secondary_key, default="primary"):
    return secondary_key if sale_type_from_payload(payload, default) == "secondary" else primary_key


def require_sale_type_access(mobile_user, payload, primary_key, secondary_key, default="primary"):
    key = sale_type_key(payload, primary_key, secondary_key, default=default)
    require_ui_access(mobile_user, key)
    return key


def contact_type_from_payload(payload, default=None):
    customer_type = (
        (payload or {}).get("customer_type")
        or (payload or {}).get("type")
        or default
        or ""
    )
    customer_type = customer_type.strip().lower() if isinstance(customer_type, str) else ""
    if customer_type not in ("distributor", "outlet"):
        raise ValidationError("Invalid customer type. Must be 'distributor' or 'outlet'.")
    return customer_type


def contact_type_key(payload, distributor_key, outlet_key, default=None):
    return outlet_key if contact_type_from_payload(payload, default) == "outlet" else distributor_key


def require_contact_type_access(mobile_user, payload, distributor_key, outlet_key, default=None):
    key = contact_type_key(payload, distributor_key, outlet_key, default=default)
    require_ui_access(mobile_user, key)
    return key


def check_mobile_model_access(mobile_user, model_name, operation):
    """Check mobile-group model access using group + implied groups."""
    policy = MobilePolicy(mobile_user)
    if not policy.has_model_access(model_name, operation, default_if_unconfigured=False):
        raise AccessDenied("You do not have access to this operation.")


def get_mobile_rule_domain(mobile_user, model_name, operation):
    """Return the effective mobile rule domain for group + implied groups."""
    return MobilePolicy(mobile_user).rule_domain(model_name, operation)


def apply_mobile_rule_domain(mobile_user, model_name, operation, domain):
    """AND a base domain with the effective mobile record-rule domain."""
    return MobilePolicy(mobile_user).apply_domain(model_name, operation, domain)


def mobile_rule_domain_allows_values(env, mobile_user, model_name, operation, values):
    """Check whether a values dict satisfies the effective mobile rule domain.

    This is useful before create requests, where there is no saved record yet.
    """
    return MobilePolicy(mobile_user).allows_values(env, model_name, operation, values)


def mobile_api_error_boundary(func):
    """Wrap a JSON mobile endpoint in the standard error boundary.

    The call is forwarded unchanged — the endpoint keeps its own signature
    (URL path params included) and still calls :func:`get_mobile_api_context`
    itself — while any exception is funnelled through
    :func:`handle_api_exception`, which rolls back the cursor, maps known
    Validation/Access/Missing/User errors to a client message, and hides
    internal detail for everything else. This replaces the identical
    ``try/except`` block every endpoint repeats. Apply it *below* ``@http.route``::

        @http.route(...)
        @mobile_api_error_boundary
        def my_endpoint(self, **payload):
            mobile_user, api_env, payload = get_mobile_api_context(payload)
            ...
    """
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except Exception as exc:
            return handle_api_exception(exc)
    return wrapper

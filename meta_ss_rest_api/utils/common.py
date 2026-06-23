# -*- coding: utf-8 -*-

import logging
from odoo.http import request
from odoo.exceptions import AccessDenied

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

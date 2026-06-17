# -*- coding: utf-8 -*-

import logging
from odoo.http import request
from odoo.exceptions import AccessDenied

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


def check_api_permission(required_permission=None):
    """Retrieves bearer token from headers, validates it, and checks the required permission if provided.

    Returns:
        res.mobile.user: The authenticated mobile user record.
    """
    auth_header = request.httprequest.headers.get("Authorization", "")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise AccessDenied("Authorization header with Bearer token is required.")

    token = auth_header[7:].strip()
    if not token:
        raise AccessDenied("Bearer token is empty.")

    Session = request.env["mobile.auth.session"].sudo()
    if required_permission:
        mobile_user, _payload, _session = Session.validate_access_token_and_permission(
            token, required_permission, check_session=True
        )
    else:
        mobile_user, _payload, _session = Session.validate_access_token(
            token, check_session=True
        )
    return mobile_user


def get_mobile_api_context(payload=None, required_permission=None, require_employee=False):
    """Validate the mobile JWT and return a trusted ORM context.

    Odoo's session selects the database and satisfies auth="user" routes. The
    bearer token remains the real mobile identity. When a mobile user is linked
    to an employee, any incoming employee_id is replaced with the trusted one
    from the token so API callers cannot impersonate another employee.
    """
    mobile_user = check_api_permission(required_permission=required_permission)
    if require_employee and not mobile_user.employee_id:
        raise AccessDenied("The mobile user is not linked to an employee.")

    trusted_payload = dict(payload or {})
    if mobile_user.employee_id:
        trusted_payload["employee_id"] = mobile_user.employee_id.id

    api_env = request.env["mobile.auth.session"].sudo().get_integration_env()
    return mobile_user, api_env, trusted_payload

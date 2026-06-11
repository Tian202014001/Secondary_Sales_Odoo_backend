# -*- coding: utf-8 -*-

import logging
from odoo.http import request
from odoo.exceptions import AccessDenied

_logger = logging.getLogger(__name__)

API_VERSION = "v1"
API_PREFIX = f"/api/{API_VERSION}"


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

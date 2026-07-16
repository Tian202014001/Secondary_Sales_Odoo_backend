# -*- coding: utf-8 -*-

from odoo import http

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    get_mobile_api_context,
    mobile_api_error_boundary,
)
from odoo.addons.meta_ss_rest_api.utils.dashboard import build_dashboard_summary


class DashboardController(http.Controller):
    """Landing-dashboard summary.

    Intentionally ungated: the dashboard home is a core screen every
    authenticated mobile user receives, so a fail-closed UI-resource gate would
    lock everyone out. Access is still bounded — the bearer token is validated
    and the employee is derived from it (``require_employee=True``), and every
    figure is scoped to that employee (or, for a manager, strictly to their own
    ``child_of`` subordinates). Registered in ``INTENTIONALLY_UNGATED_MATRIX``
    in ``tests/test_endpoint_access_control.py``.
    """

    @http.route(
        f"{API_PREFIX}/dashboard/summary",
        type="json",
        auth="user",
        methods=["POST"],
    )
    @mobile_api_error_boundary
    def dashboard_summary(self, **payload):
        mobile_user, api_env, _payload = get_mobile_api_context(
            payload, require_employee=True
        )
        data = build_dashboard_summary(api_env, mobile_user.employee_id)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Dashboard summary retrieved successfully.",
            "data": data,
        }

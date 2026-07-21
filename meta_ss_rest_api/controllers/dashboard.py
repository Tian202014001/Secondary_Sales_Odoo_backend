# -*- coding: utf-8 -*-

from odoo import http

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    get_mobile_api_context,
    mobile_api_error_boundary,
)
from odoo.addons.meta_ss_rest_api.utils.mtd_summary import (
    build_mtd_summary,
    resolve_dashboard_range,
    resolve_scoped_employee,
)


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
        mobile_user, api_env, payload = get_mobile_api_context(
            payload, require_employee=True
        )
        preset, date_from, date_to = resolve_dashboard_range(payload)
        scoped_employee = resolve_scoped_employee(
            api_env,
            mobile_user.employee_id.id,
            payload.get("scope_employee_id"),
        )
        data = build_mtd_summary(
            api_env,
            scoped_employee,
            mobile_user,
            date_from,
            date_to,
            preset=preset,
        )
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Dashboard summary retrieved successfully.",
            "data": data,
        }

# -*- coding: utf-8 -*-

from odoo import fields, http
from odoo.http import request
from odoo.addons.meta_ss_rest_api.utils.common import API_PREFIX, API_VERSION, error_response
from ..utils.route_visits import (
    serialize_route_visit_summary,
    serialize_route_visit_details,
    perform_route_visit_action,
)


class RouteVisitController(http.Controller):

    @http.route(f"{API_PREFIX}/routes/<int:route_id>/visits", type="json", auth="public", methods=["POST"])
    def get_route_visit_history(self, route_id, **payload):
        """Fetch the list of all daily sessions for a specific route."""
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response("validation_error", "employee_id is required")

        visits = request.env["sale.route.visit"].sudo().search([
            ("route_id", "=", route_id),
            ("employee_id", "=", employee_id),
            ("state", "!=", "draft"),
        ], order="visit_date desc, id desc")

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Route visit history fetched successfully",
            "data": [serialize_route_visit_summary(v) for v in visits],
        }

    @http.route(f"{API_PREFIX}/route-visits", type="json", auth="public", methods=["POST"])
    def start_route_visit(self, **payload):
        """Start a new route visit for the day or return the existing active one."""
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response("validation_error", "employee_id is required")

        route_id = payload.get("route_id")
        if not route_id:
            return error_response("validation_error", "route_id is required")

        today = fields.Date.context_today(request.env.user)

        existing_visit = request.env["sale.route.visit"].sudo().search([
            ("route_id", "=", route_id),
            ("employee_id", "=", employee_id),
            ("visit_date", "=", today),
        ], limit=1)

        if existing_visit:
            if existing_visit.state == "draft":
                existing_visit.action_start()
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Existing route visit retrieved",
                "data": serialize_route_visit_summary(existing_visit),
            }

        try:
            new_visit = request.env["sale.route.visit"].sudo().create({
                "route_id": route_id,
                "employee_id": employee_id,
                "visit_date": today,
            })
            new_visit.action_start()
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Route visit started successfully",
                "data": serialize_route_visit_summary(new_visit),
            }
        except Exception as exc:
            request.env.cr.rollback()
            return error_response("server_error", str(exc))

    @http.route(f"{API_PREFIX}/route-visits/<int:visit_id>", type="json", auth="public", methods=["POST"])
    def get_route_visit_details(self, visit_id, **payload):
        """Fetch a specific route visit and its lines."""
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response("validation_error", "employee_id is required")

        visit = request.env["sale.route.visit"].sudo().browse(visit_id)
        if not visit.exists():
            return error_response("not_found", "Route visit not found")

        if visit.employee_id.id != int(employee_id):
            return error_response("forbidden", "You do not have permission to view this route visit")

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Route visit details fetched successfully",
            "data": serialize_route_visit_details(visit),
        }

    @http.route(f"{API_PREFIX}/route-visits/<int:visit_id>/action", type="json", auth="public", methods=["POST"])
    def execute_route_visit_action(self, visit_id, **payload):
        """Unified endpoint to perform actions: check_in, check_out, skip, complete."""
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response("validation_error", "employee_id is required")

        visit = request.env["sale.route.visit"].sudo().browse(visit_id)
        if not visit.exists():
            return error_response("not_found", "Route visit not found")

        if visit.employee_id.id != int(employee_id):
            return error_response("forbidden", "You do not have permission to modify this route visit")

        result = perform_route_visit_action(request.env, visit_id, payload)

        if "error" in result:
            return error_response("validation_error", result["error"])

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Action executed successfully",
            "data": result,
        }

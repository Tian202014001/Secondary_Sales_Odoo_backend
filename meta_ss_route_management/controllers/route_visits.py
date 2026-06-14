# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.addons.meta_ss_rest_api.utils.common import _response
from odoo.addons.meta_ss_rest_api.utils.helpers import extract_employee_id
from ..utils.route_visits import serialize_route_visit_summary, serialize_route_visit_details, perform_route_visit_action

class RouteVisitController(http.Controller):

    @http.route(["/api/v1/routes/<int:route_id>/visits"], type="json", auth="user", methods=["GET"])
    def get_route_visit_history(self, route_id, **kwargs):
        """Fetch the list of all daily sessions for a specific route"""
        employee_id, error_response = extract_employee_id(request)
        if error_response:
            return error_response

        # Get all non-draft visits for this route and employee, ordered by visit_date desc
        visits = request.env["sale.route.visit"].sudo().search([
            ("route_id", "=", route_id),
            ("employee_id", "=", employee_id),
            ("state", "!=", "draft")
        ], order="visit_date desc, id desc")

        data = [serialize_route_visit_summary(v) for v in visits]
        return _response(200, "Route visit history fetched successfully", data)

    @http.route(["/api/v1/route-visits"], type="json", auth="user", methods=["POST"])
    def start_route_visit(self, **kwargs):
        """Start a new route visit for the day or fetch existing active one"""
        employee_id, error_response = extract_employee_id(request)
        if error_response:
            return error_response

        payload = request.get_json_data()
        route_id = payload.get("route_id")

        if not route_id:
            return _response(400, "route_id is required")

        today = fields.Date.context_today(request.env.user) if "odoo.fields" in globals() else request.env["sale.route.visit"].sudo()._fields['visit_date'].default(request.env["sale.route.visit"].sudo())
        
        # In Odoo 18, we can use fields.Date.context_today directly if imported. Let's do it safely.
        from odoo import fields
        today = fields.Date.context_today(request.env.user)

        # Check if already exists for today
        existing_visit = request.env["sale.route.visit"].sudo().search([
            ("route_id", "=", route_id),
            ("employee_id", "=", employee_id),
            ("visit_date", "=", today),
        ], limit=1)

        if existing_visit:
            if existing_visit.state == "draft":
                existing_visit.action_start()
            return _response(200, "Existing route visit retrieved", serialize_route_visit_summary(existing_visit))

        # Create new visit
        try:
            new_visit = request.env["sale.route.visit"].sudo().create({
                "route_id": route_id,
                "employee_id": employee_id,
                "visit_date": today,
            })
            new_visit.action_start()
            return _response(201, "Route visit started successfully", serialize_route_visit_summary(new_visit))
        except Exception as e:
            return _response(500, f"Error starting route visit: {str(e)}")

    @http.route(["/api/v1/route-visits/<int:visit_id>"], type="json", auth="user", methods=["GET"])
    def get_route_visit_details(self, visit_id, **kwargs):
        """Fetch a specific route visit and its lines"""
        employee_id, error_response = extract_employee_id(request)
        if error_response:
            return error_response

        visit = request.env["sale.route.visit"].sudo().browse(visit_id)
        if not visit.exists():
            return _response(404, "Route visit not found")

        if visit.employee_id.id != employee_id:
            return _response(403, "You do not have permission to view this route visit")

        data = serialize_route_visit_details(visit)
        return _response(200, "Route visit details fetched successfully", data)

    @http.route(["/api/v1/route-visits/<int:visit_id>/action"], type="json", auth="user", methods=["POST"])
    def execute_route_visit_action(self, visit_id, **kwargs):
        """Unified endpoint to perform actions (check_in, check_out, skip, complete)"""
        employee_id, error_response = extract_employee_id(request)
        if error_response:
            return error_response

        visit = request.env["sale.route.visit"].sudo().browse(visit_id)
        if not visit.exists():
            return _response(404, "Route visit not found")

        if visit.employee_id.id != employee_id:
            return _response(403, "You do not have permission to modify this route visit")

        payload = request.get_json_data()
        
        result = perform_route_visit_action(request.env.sudo(), visit_id, payload)
        
        if "error" in result:
            return _response(400, result["error"])
            
        return _response(200, "Action executed successfully", result)

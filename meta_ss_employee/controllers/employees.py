# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    check_api_permission,
    error_response,
)
from odoo.addons.meta_ss_employee.utils.employees import (
    build_employee_domain,
    get_employee_pagination,
    prepare_employee_update_values,
    prepare_employee_values,
    serialize_employee,
)


class MetaSSEmployeeController(http.Controller):

    @http.route(f"{API_PREFIX}/employees", type="json", auth="public", methods=["POST"])
    def get_employees(self, **payload):
        """Return employees for assignment dropdowns.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "distributor_id": 3,
                    "search": "Audrey",
                    "page": 1,
                    "page_size": 20
                },
                "id": 1
            }
        """
        try:
            # check_api_permission()
            domain = build_employee_domain(request.env, payload)
            limit, offset, page, page_size = get_employee_pagination(payload)
            Employee = request.env["hr.employee"].sudo()
            employees = Employee.search(domain, limit=limit, offset=offset, order="name")
            total = Employee.search_count(domain)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Employees fetched successfully.",
                "data": [serialize_employee(employee) for employee in employees],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                },
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching employees.",
            )

    @http.route(f"{API_PREFIX}/employees/create", type="json", auth="public", methods=["POST"])
    def create_employee(self, **payload):
        """Create a new employee (Sales Officer) with distributor tagging and optional routes.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "name": "Sales Officer A",
                    "email": "so_a@example.com",
                    "phone": "01700000001",
                    "distributor_id": 3,
                    "assigned_route_ids": [10, 11]
                },
                "id": 1
            }
        """
        try:
            # check_api_permission()
            vals = prepare_employee_values(request.env, payload)
            employee = request.env["hr.employee"].sudo().create(vals)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Employee created successfully.",
                "data": serialize_employee(employee),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while creating employee.",
            )

    @http.route(f"{API_PREFIX}/employees/<int:employee_id>", type="json", auth="public", methods=["POST"])
    def get_employee(self, employee_id, **payload):
        """Return one employee detail by id.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {},
                "id": 1
            }
        """
        try:
            # check_api_permission()
            employee = request.env["hr.employee"].sudo().browse(employee_id).exists()
            if not employee:
                raise ValidationError("Employee not found.")

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Employee details fetched successfully.",
                "data": serialize_employee(employee),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching employee details.",
            )

    @http.route(f"{API_PREFIX}/employees/<int:employee_id>/update", type="json", auth="public", methods=["POST"])
    def update_employee(self, employee_id, **payload):
        """Update an existing employee details and route mappings.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "name": "Updated Name",
                    "assigned_route_ids": [10]
                },
                "id": 1
            }
        """
        try:
            # check_api_permission()
            employee = request.env["hr.employee"].sudo().browse(employee_id).exists()
            if not employee:
                raise ValidationError("Employee not found.")

            vals = prepare_employee_update_values(request.env, payload, employee)
            if vals:
                employee.write(vals)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Employee updated successfully.",
                "data": serialize_employee(employee),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while updating employee.",
            )

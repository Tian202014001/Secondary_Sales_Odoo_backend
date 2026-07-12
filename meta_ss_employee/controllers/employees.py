# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    mobile_api_error_boundary,
    require_ui_access,
)
from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey
from odoo.addons.meta_ss_employee.utils.employees import (
    build_employee_domain,
    get_employee_for_payload,
    get_employee_pagination,
    prepare_employee_update_values,
    prepare_employee_values,
    serialize_employee,
)


class MetaSSEmployeeController(http.Controller):

    @http.route(f"{API_PREFIX}/employees", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
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
        _mobile_user, api_env, payload = get_mobile_api_context(payload)
        require_ui_access(_mobile_user, AccessKey.DASHBOARD_SALES_OFFICERS_LIST)
        domain = build_employee_domain(api_env, payload)
        limit, offset, page, page_size = get_employee_pagination(payload)
        Employee = api_env["hr.employee"]
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

    @http.route(f"{API_PREFIX}/employees/create", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
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
        _mobile_user, api_env, payload = get_mobile_api_context(payload)
        require_ui_access(_mobile_user, AccessKey.DASHBOARD_SALES_OFFICERS_CREATE)
        vals = prepare_employee_values(api_env, payload)
        employee = api_env["hr.employee"].create(vals)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Employee created successfully.",
            "data": serialize_employee(employee),
        }

    @http.route(f"{API_PREFIX}/employees/<int:employee_id>", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
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
        _mobile_user, api_env, payload = get_mobile_api_context(payload)
        require_ui_access(_mobile_user, AccessKey.DASHBOARD_SALES_OFFICERS_DETAIL)
        employee = get_employee_for_payload(api_env, employee_id, payload)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Employee details fetched successfully.",
            "data": serialize_employee(employee),
        }

    @http.route(f"{API_PREFIX}/employees/<int:employee_id>/update", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
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
        _mobile_user, api_env, payload = get_mobile_api_context(payload)
        require_ui_access(_mobile_user, AccessKey.DASHBOARD_SALES_OFFICERS_CREATE)
        employee = get_employee_for_payload(api_env, employee_id, payload)

        vals = prepare_employee_update_values(api_env, payload, employee)
        if vals:
            employee.write(vals)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Employee updated successfully.",
            "data": serialize_employee(employee),
        }


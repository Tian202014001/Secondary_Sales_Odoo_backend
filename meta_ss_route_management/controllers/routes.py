# -*- coding: utf-8 -*-

import math
from datetime import datetime, timezone

from odoo import http, fields

def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    mobile_api_error_boundary,
    handle_api_exception,
    require_ui_access,
)
from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey
from odoo.addons.meta_ss_route_management.utils.routes import (
    build_employee_route_domain,
    get_pagination,
    prepare_route_outlet_line_values,
    prepare_route_values,
    serialize_route_detail,
    serialize_route_outlet_line,
    serialize_routes,
)


def _mobile_datetime_to_odoo(value):
    """Accept mobile ISO timestamps and return an Odoo datetime value."""
    if not value:
        return value
    if isinstance(value, datetime):
        date_value = value
    elif isinstance(value, str):
        clean_value = value.strip()
        if not clean_value:
            return clean_value
        if clean_value.endswith("Z"):
            clean_value = f"{clean_value[:-1]}+00:00"
        try:
            date_value = datetime.fromisoformat(clean_value)
        except ValueError:
            from odoo import fields

            return fields.Datetime.to_datetime(value)
    else:
        return value

    if date_value.tzinfo:
        date_value = date_value.astimezone(timezone.utc).replace(tzinfo=None)

    from odoo import fields

    return fields.Datetime.to_string(date_value)


class MetaSSRouteController(http.Controller):

    @http.route(f"{API_PREFIX}/ss/routes", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_employee_routes(self, **payload):
        """Return routes assigned to a requested employee.

        List request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "search": "route name or code",
                    "distributor_id": 3,
                    "route_id": 12,
                    "active": true,
                    "page": 1,
                    "page_size": 20
                },
                "id": 1
            }

        Create request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "name": "Route A",
                    "code": "R-A",
                    "distributor_id": 3,
                    "employee_ids": [7, 8]
                },
                "id": 1
            }

        List response body example:
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "success": true,
                    "api_version": API_VERSION,
                    "message": "Routes fetched successfully.",
                    "data": [
                        {
                            "id": 12,
                            "name": "Route A",
                            "code": "R-A",
                            "active": true,
                            "distributor": {
                                "id": 3,
                                "name": "Distributor A"
                            },
                            "employees": [
                                {
                                    "id": 7,
                                    "name": "Sales Officer 1"
                                }
                            ],
                            "outlet_count": 10
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "page_size": 20,
                        "total": 1
                    }
                }
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_ROUTES_LIST)
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response(
                "missing_employee_id",
                "'employee_id' is required.",
            )

        employee = api_env["hr.employee"].browse(int(employee_id)).exists()
        if not employee:
            return error_response(
                "employee_not_found",
                "No employee was found for the provided 'employee_id'.",
            )

        Route = api_env["sale.route"].sudo()
        domain = build_employee_route_domain(employee, payload)
        limit, offset, page, page_size = get_pagination(payload)
        routes = Route.search(domain, limit=limit, offset=offset, order="name")
        total = Route.search_count(domain)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Routes fetched successfully.",
            "data": serialize_routes(routes),
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }

    @http.route(f"{API_PREFIX}/ss/routes/create", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def create_employee_route(self, **payload):
        """Create a route assigned to the requested employee.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "name": "Route A",
                    "code": "R-A",
                    "distributor_id": 3,
                    "employee_ids": [7, 8]
                },
                "id": 1
            }

        Response body example:
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "success": true,
                    "api_version": API_VERSION,
                    "message": "Route created successfully.",
                    "data": {
                        "id": 12,
                        "name": "Route A",
                        "code": "R-A",
                        "active": true,
                        "distributor": {
                            "id": 3,
                            "name": "Distributor A",
                            "phone": null,
                            "mobile": "01700000000",
                            "email": null
                        },
                        "employees": [
                            {
                                "id": 7,
                                "name": "Sales Officer 1",
                                "work_phone": null,
                                "work_email": "so1@example.com"
                            }
                        ],
                        "outlets": [],
                        "outlet_count": 0
                    }
                }
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_ROUTES_CREATE)
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response(
                "missing_employee_id",
                "'employee_id' is required.",
            )

        employee = api_env["hr.employee"].browse(int(employee_id)).exists()
        if not employee:
            return error_response(
                "employee_not_found",
                "No employee was found for the provided 'employee_id'.",
            )

        route = api_env["sale.route"].create(prepare_route_values(
            api_env,
            payload,
            employee,
            create=True,
        ))
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Route created successfully.",
            "data": serialize_route_detail(route),
        }

    @http.route(f"{API_PREFIX}/ss/routes/<int:route_id>/outlets/add", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def add_employee_route_outlet(self, route_id, **payload):
        """Add an existing or newly created outlet to a selected route.

        Existing outlet request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "outlet_id": 31,
                    "sequence": 10,
                    "expected_visit_time": 9.5
                },
                "id": 1
            }

        New outlet request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "name": "New Outlet A",
                    "mobile": "01800000000",
                    "street": "Road 1",
                    "city": "Dhaka",
                    "sequence": 20,
                    "expected_visit_time": 10.5
                },
                "id": 1
            }

        Response body example:
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "success": true,
                    "api_version": API_VERSION,
                    "message": "Outlet added to route successfully.",
                    "data": {
                        "line_id": 20,
                        "id": 31,
                        "name": "Outlet A",
                        "sequence": 10,
                        "expected_visit_time": 9.5,
                        "phone": null,
                        "mobile": "01800000000",
                        "email": null,
                        "street": "Road 1",
                        "street2": null,
                        "city": "Dhaka",
                        "zip": null,
                        "vat": null,
                        "active": true
                    }
                }
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_ROUTES_ADD_OUTLET)
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response(
                "missing_employee_id",
                "'employee_id' is required.",
            )

        employee = api_env["hr.employee"].browse(int(employee_id)).exists()
        if not employee:
            return error_response(
                "employee_not_found",
                "No employee was found for the provided 'employee_id'.",
            )

        route = api_env["sale.route"].search([
            ("id", "=", route_id),
            ("active", "=", True),
            ("ss_employee_id", "child_of", employee.id),
        ], limit=1)
        if not route:
            return error_response(
                "route_not_found",
                "No active route was found for the provided route and employee.",
            )

        line_values = prepare_route_outlet_line_values(api_env, payload)
        existing_line = api_env["sale.route.line"].search([
            ("route_id", "=", route.id),
            ("outlet_id", "=", line_values["outlet_id"]),
        ], limit=1)
        if existing_line:
            existing_line.write(line_values)
            route_line = existing_line
            message = "Outlet already existed on route and was updated."
        else:
            line_values["route_id"] = route.id
            route_line = api_env["sale.route.line"].create(line_values)
            message = "Outlet added to route successfully."

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": message,
            "data": serialize_route_outlet_line(route_line),
        }

    @http.route(f"{API_PREFIX}/ss/routes/<int:route_id>", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_employee_route_detail(self, route_id, **payload):
        """Return one route detail by route id for a requested employee.

        Detail request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7
                },
                "id": 1
            }

        Detail response body example:
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "success": true,
                    "api_version": API_VERSION,
                    "message": "Route fetched successfully.",
                    "data": {
                        "id": 12,
                        "name": "Route A",
                        "code": "R-A",
                        "active": true,
                        "distributor": {
                            "id": 3,
                            "name": "Distributor A",
                            "phone": null,
                            "mobile": "01700000000",
                            "email": null
                        },
                        "employees": [
                            {
                                "id": 7,
                                "name": "Sales Officer 1",
                                "work_phone": null,
                                "work_email": "so1@example.com"
                            }
                        ],
                        "outlets": [
                            {
                                "line_id": 20,
                                "id": 31,
                                "name": "Outlet A",
                                "sequence": 10,
                                "expected_visit_time": 9.5,
                                "phone": null,
                                "mobile": "01800000000",
                                "email": null,
                                "street": "Road 1",
                                "street2": null,
                                "city": "Dhaka",
                                "active": true
                            }
                        ],
                        "outlet_count": 1
                    }
                }
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_ROUTES_DETAIL)
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response(
                "missing_employee_id",
                "'employee_id' is required.",
            )

        employee = api_env["hr.employee"].browse(int(employee_id)).exists()
        if not employee:
            return error_response(
                "employee_not_found",
                "No employee was found for the provided 'employee_id'.",
            )

        route = api_env["sale.route"].sudo().search([
            ("id", "=", route_id),
            ("ss_employee_id", "child_of", employee.id),
            ("active", "=", True),
        ], limit=1)
        if not route:
            return error_response(
                "route_not_found",
                "No route was found for the provided route and employee.",
            )

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Route fetched successfully.",
            "data": serialize_route_detail(route),
        }

    @http.route(f"{API_PREFIX}/ss/routes/<int:route_id>/update", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def update_employee_route(self, route_id, **payload):
        """Update a route assigned to the requested employee.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "name": "Updated Route A",
                    "code": "R-A",
                    "distributor_id": 3,
                    "employee_ids": [7, 8],
                    "active": true,
                    "outlets": [
                        {
                            "outlet_id": 31,
                            "sequence": 10,
                            "expected_visit_time": 9.5,
                            "active": true
                        },
                        {
                            "name": "New Outlet A",
                            "mobile": "01800000000",
                            "street": "Road 1",
                            "city": "Dhaka",
                            "sequence": 20,
                            "expected_visit_time": 10.5,
                            "active": true
                        }
                    ]
                },
                "id": 1
            }

        Response body example:
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "success": true,
                    "api_version": API_VERSION,
                    "message": "Route updated successfully.",
                    "data": {
                        "id": 12,
                        "name": "Updated Route A",
                        "code": "R-A",
                        "active": true,
                        "outlets": [],
                        "outlet_count": 0
                    }
                }
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_ROUTES_CREATE)
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response(
                "missing_employee_id",
                "'employee_id' is required.",
            )

        employee = api_env["hr.employee"].browse(int(employee_id)).exists()
        if not employee:
            return error_response(
                "employee_not_found",
                "No employee was found for the provided 'employee_id'.",
            )

        route = api_env["sale.route"].sudo().search([
            ("id", "=", route_id),
            ("ss_employee_id", "child_of", employee.id),
        ], limit=1)
        if not route:
            return error_response(
                "route_not_found",
                "No route was found for the provided route and employee.",
            )

        values = prepare_route_values(api_env, payload, employee)
        if not values:
            return error_response(
                "missing_update_values",
                "At least one route field is required for update.",
            )

        route.write(values)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Route updated successfully.",
            "data": serialize_route_detail(route),
        }

    @http.route(f"{API_PREFIX}/ss/routes/<int:route_id>/outlets/<int:outlet_id>/remove", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def remove_employee_route_outlet(self, route_id, outlet_id, **payload):
        """Remove an outlet from a route.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7
                },
                "id": 1
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_ROUTES_ADD_OUTLET)
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response(
                "missing_employee_id",
                "'employee_id' is required.",
            )

        employee = api_env["hr.employee"].browse(int(employee_id)).exists()
        if not employee:
            return error_response(
                "employee_not_found",
                "No employee was found for the provided 'employee_id'.",
            )

        route = api_env["sale.route"].sudo().search([
            ("id", "=", route_id),
            ("ss_employee_id", "child_of", employee.id),
        ], limit=1)
        if not route:
            return error_response(
                "route_not_found",
                "No route was found for the provided route and employee.",
            )

        route_line = api_env["sale.route.line"].sudo().search([
            ("route_id", "=", route.id),
            ("outlet_id", "=", int(outlet_id)),
        ], limit=1)
        if not route_line:
            return error_response(
                "outlet_not_on_route",
                "The selected outlet is not assigned to this route.",
            )

        route_line.unlink()
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Outlet removed from route successfully.",
        }



# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import API_PREFIX, API_VERSION, error_response
from odoo.addons.meta_ss_rest_api.utils.routes import (
    build_employee_route_domain,
    get_pagination,
    has_route_create_payload,
    has_route_update_payload,
    prepare_route_outlet_line_values,
    prepare_route_values,
    serialize_route_detail,
    serialize_route_outlet_line,
    serialize_routes,
)


class MetaSSRouteController(http.Controller):

    @http.route(f"{API_PREFIX}/ss/routes", type="json", auth="public", methods=["POST"])
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
                    "api_version": "v1",
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
        try:
            employee_id = payload.get("employee_id")
            if not employee_id:
                return error_response(
                    "missing_employee_id",
                    "'employee_id' is required.",
                )

            employee = request.env["hr.employee"].sudo().browse(int(employee_id)).exists()
            if not employee:
                return error_response(
                    "employee_not_found",
                    "No employee was found for the provided 'employee_id'.",
                )

            Route = request.env["sale.route"].sudo()
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
        except (TypeError, ValueError):
            return error_response(
                "invalid_employee_id",
                "'employee_id' must be a valid integer.",
            )
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching routes.",
            )

    @http.route(f"{API_PREFIX}/ss/routes/create", type="json", auth="public", methods=["POST"])
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
                    "api_version": "v1",
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
        try:
            employee_id = payload.get("employee_id")
            if not employee_id:
                return error_response(
                    "missing_employee_id",
                    "'employee_id' is required.",
                )

            employee = request.env["hr.employee"].sudo().browse(int(employee_id)).exists()
            if not employee:
                return error_response(
                    "employee_not_found",
                    "No employee was found for the provided 'employee_id'.",
                )

            route = request.env["sale.route"].sudo().create(prepare_route_values(
                request.env,
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
        except (TypeError, ValueError):
            return error_response(
                "invalid_employee_id",
                "'employee_id' must be a valid integer.",
            )
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while creating the route.",
            )

    @http.route(f"{API_PREFIX}/ss/routes/<int:route_id>/outlets/add", type="json", auth="public", methods=["POST"])
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
                    "api_version": "v1",
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
        try:
            employee_id = payload.get("employee_id")
            if not employee_id:
                return error_response(
                    "missing_employee_id",
                    "'employee_id' is required.",
                )

            employee = request.env["hr.employee"].sudo().browse(int(employee_id)).exists()
            if not employee:
                return error_response(
                    "employee_not_found",
                    "No employee was found for the provided 'employee_id'.",
                )

            route = request.env["sale.route"].sudo().search([
                ("id", "=", route_id),
                ("active", "=", True),
                ("ss_employee_ids", "in", [employee.id]),
            ], limit=1)
            if not route:
                return error_response(
                    "route_not_found",
                    "No active route was found for the provided route and employee.",
                )

            line_values = prepare_route_outlet_line_values(request.env, payload)
            existing_line = request.env["sale.route.line"].sudo().search([
                ("route_id", "=", route.id),
                ("outlet_id", "=", line_values["outlet_id"]),
            ], limit=1)
            if existing_line:
                existing_line.write(line_values)
                route_line = existing_line
                message = "Outlet already existed on route and was updated."
            else:
                line_values["route_id"] = route.id
                route_line = request.env["sale.route.line"].sudo().create(line_values)
                message = "Outlet added to route successfully."

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": message,
                "data": serialize_route_outlet_line(route_line),
            }
        except (TypeError, ValueError):
            return error_response(
                "invalid_employee_id",
                "'employee_id' must be a valid integer.",
            )
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while adding the route outlet.",
            )

    @http.route(f"{API_PREFIX}/ss/routes/<int:route_id>", type="json", auth="public", methods=["POST"])
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
                    "api_version": "v1",
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
        try:
            employee_id = payload.get("employee_id")
            if not employee_id:
                return error_response(
                    "missing_employee_id",
                    "'employee_id' is required.",
                )

            employee = request.env["hr.employee"].sudo().browse(int(employee_id)).exists()
            if not employee:
                return error_response(
                    "employee_not_found",
                    "No employee was found for the provided 'employee_id'.",
                )

            route = request.env["sale.route"].sudo().search([
                ("id", "=", route_id),
                ("ss_employee_ids", "in", [employee.id]),
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
        except (TypeError, ValueError):
            return error_response(
                "invalid_employee_id",
                "'employee_id' must be a valid integer.",
            )
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching the route.",
            )

    @http.route(f"{API_PREFIX}/ss/routes/<int:route_id>/update", type="json", auth="public", methods=["POST"])
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
                    "api_version": "v1",
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
        try:
            employee_id = payload.get("employee_id")
            if not employee_id:
                return error_response(
                    "missing_employee_id",
                    "'employee_id' is required.",
                )

            employee = request.env["hr.employee"].sudo().browse(int(employee_id)).exists()
            if not employee:
                return error_response(
                    "employee_not_found",
                    "No employee was found for the provided 'employee_id'.",
                )

            route = request.env["sale.route"].sudo().search([
                ("id", "=", route_id),
                ("ss_employee_ids", "in", [employee.id]),
            ], limit=1)
            if not route:
                return error_response(
                    "route_not_found",
                    "No route was found for the provided route and employee.",
                )

            values = prepare_route_values(request.env, payload, employee)
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
        except (TypeError, ValueError):
            return error_response(
                "invalid_employee_id",
                "'employee_id' must be a valid integer.",
            )
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while updating the route.",
            )

    @http.route(f"{API_PREFIX}/ss/routes/<int:route_id>/outlets/<int:outlet_id>/remove", type="json", auth="public", methods=["POST"])
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
        try:
            employee_id = payload.get("employee_id")
            if not employee_id:
                return error_response(
                    "missing_employee_id",
                    "'employee_id' is required.",
                )

            employee = request.env["hr.employee"].sudo().browse(int(employee_id)).exists()
            if not employee:
                return error_response(
                    "employee_not_found",
                    "No employee was found for the provided 'employee_id'.",
                )

            route = request.env["sale.route"].sudo().search([
                ("id", "=", route_id),
                ("ss_employee_ids", "in", [employee.id]),
            ], limit=1)
            if not route:
                return error_response(
                    "route_not_found",
                    "No route was found for the provided route and employee.",
                )

            route_line = request.env["sale.route.line"].sudo().search([
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
        except (TypeError, ValueError):
            return error_response(
                "invalid_payload",
                "Invalid data types in route parameters.",
            )
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while removing the outlet.",
            )

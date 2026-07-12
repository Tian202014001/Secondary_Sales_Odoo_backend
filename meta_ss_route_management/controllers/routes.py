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

    @http.route(f"{API_PREFIX}/visits", type="json", auth="user", methods=["POST"], csrf=False)
    @mobile_api_error_boundary
    def get_employee_visits(self, **payload):
        """Get paginated list of visits."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_VISITS_LIST)
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response("missing_employee_id", "'employee_id' is required.")

        domain = [("employee_id", "child_of", int(employee_id))]

        visit_type = payload.get("visit_type")
        if visit_type and visit_type != "all":
            domain.append(("visit_type", "=", visit_type))

        route_id = payload.get("route_id")
        if route_id:
            route_line_outlets = api_env["sale.route.line"].sudo().search([("route_id", "=", int(route_id))]).mapped("outlet_id.id")
            if route_line_outlets:
                domain.append(("outlet_id", "in", route_line_outlets))
            else:
                domain.append(("id", "=", 0))

        search = (payload.get("search") or "").strip()
        if search:
            domain.append(("outlet_id.name", "ilike", search))

        limit, offset, page, page_size = get_pagination(payload)
        Visit = api_env["outlet.visit"].sudo()

        visits = Visit.search(domain, limit=limit, offset=offset, order="check_in_time desc, id desc")
        total = Visit.search_count(domain)

        data = []
        for visit in visits:
            data.append({
                "id": visit.id,
                "employee_id": visit.employee_id.id,
                "employee_name": visit.employee_id.name,
                "outlet_id": visit.outlet_id.id,
                "outlet_name": visit.outlet_id.name,
                "check_in_time": str(visit.check_in_time) if visit.check_in_time else None,
                "check_out_time": str(visit.check_out_time) if visit.check_out_time else None,
                "visit_type": visit.visit_type,
                "visited_with_name": visit.visited_with_id.name if visit.visited_with_id else None,
            })

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Visits fetched successfully.",
            "data": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }

    @http.route(f"{API_PREFIX}/visits/create", type="json", auth="user", methods=["POST"], csrf=False)
    @mobile_api_error_boundary
    def create_visit(self, **payload):
        """Create a new outlet.visit record."""
        from odoo import fields
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_VISITS_CHECK_IN)

        employee_id = payload.get("employee_id")
        outlet_id = payload.get("outlet_id")
        check_in_time = _mobile_datetime_to_odoo(payload.get("check_in_time")) or fields.Datetime.now()

        lat = payload.get("latitude")
        lon = payload.get("longitude")

        if not employee_id:
            raise ValidationError("'employee_id' is required.")
        if not outlet_id:
            raise ValidationError("'outlet_id' is required.")
        if not lat or not lon:
            raise ValidationError("latitude and longitude are required to check in to an outlet.")

        try:
            lat = float(lat)
            lon = float(lon)
        except ValueError:
            raise ValidationError("Invalid coordinates format.")

        outlet = api_env["res.partner"].sudo().browse(int(outlet_id))
        if not outlet.exists():
            raise ValidationError("Outlet not found.")

        o_lat = outlet.partner_latitude
        o_lon = outlet.partner_longitude
        # Fallback to 50 meters if the radius is not configured
        radius = getattr(outlet, 'ss_attendance_radius', 50.0) or 50.0

        if not o_lat or not o_lon:
            raise ValidationError("This outlet does not have GPS coordinates set. Please update the outlet location first.")

        distance = haversine_distance(lat, lon, o_lat, o_lon)
        if distance > radius:
            raise ValidationError("You must be within the outlet's radius to check in.")

        visit = api_env["outlet.visit"].sudo().create({
            "employee_id": int(employee_id),
            "outlet_id": int(outlet_id),
            "check_in_time": check_in_time,
            "visit_type": payload.get("visit_type", "standard"),
        })

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Visit created successfully.",
            "data": {
                "id": visit.id,
                "employee_id": visit.employee_id.id,
                "outlet_id": visit.outlet_id.id,
                "check_in_time": str(visit.check_in_time) if visit.check_in_time else None,
                "visit_type": visit.visit_type,
            }
        }

    @http.route(f"{API_PREFIX}/visits/<int:visit_id>/update", type="json", auth="user", methods=["POST"], csrf=False)
    @mobile_api_error_boundary
    def update_visit(self, visit_id, **payload):
        """Update an existing outlet.visit record (e.g., set check_out_time)."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_VISITS_CHECK_OUT)
        employee_id = payload.get("employee_id")
        if not employee_id:
            raise ValidationError("'employee_id' is required.")
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'employee_id' must be a valid integer id.") from exc

        visit = api_env["outlet.visit"].sudo().search([
            ("id", "=", visit_id),
            ("employee_id", "child_of", employee_id),
        ], limit=1)
        if not visit:
            raise ValidationError("No visit was found for the provided id.")

        lat = payload.get("latitude")
        lon = payload.get("longitude")

        if lat and lon:
            try:
                lat = float(lat)
                lon = float(lon)
            except ValueError:
                raise ValidationError("Invalid coordinates format.")

            outlet = visit.outlet_id
            o_lat = outlet.partner_latitude
            o_lon = outlet.partner_longitude
            radius = getattr(outlet, 'ss_attendance_radius', 50.0) or 50.0

            if not o_lat or not o_lon:
                raise ValidationError("This outlet does not have GPS coordinates set.")

            distance = haversine_distance(lat, lon, o_lat, o_lon)
            if distance > radius:
                raise ValidationError("You must be within the outlet's radius to check out.")

        vals = {}
        if "check_out_time" in payload:
            vals["check_out_time"] = _mobile_datetime_to_odoo(payload["check_out_time"])
        if "visit_type" in payload:
            vals["visit_type"] = payload["visit_type"]
        if "visited_with_id" in payload:
            vals["visited_with_id"] = int(payload["visited_with_id"])

        if vals:
            visit.write(vals)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Visit updated successfully.",
            "data": {
                "id": visit.id,
                "employee_id": visit.employee_id.id,
                "outlet_id": visit.outlet_id.id,
                "check_in_time": str(visit.check_in_time) if visit.check_in_time else None,
                "check_out_time": str(visit.check_out_time) if visit.check_out_time else None,
                "visit_type": visit.visit_type,
            }
        }

    @http.route(f"{API_PREFIX}/visits/today", type="json", auth="user", methods=["POST"], csrf=False)
    @mobile_api_error_boundary
    def get_today_visits(self, **payload):
        """Get today's visits (active and checked out) for the employee."""
        import datetime
        import pytz
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_VISITS_LIST)
        employee_id = payload.get("employee_id")
        if not employee_id:
            return error_response("missing_employee_id", "'employee_id' is required.")

        user_tz = pytz.timezone(request.env.user.tz or 'UTC')
        today_user = datetime.datetime.now(user_tz).date()

        start_dt = datetime.datetime.combine(today_user, datetime.time.min)
        start_dt_utc = user_tz.localize(start_dt).astimezone(pytz.utc).replace(tzinfo=None)

        visits = api_env["outlet.visit"].sudo().search([
            ("employee_id", "=", int(employee_id)),
            "|",
            ("check_in_time", ">=", start_dt_utc),
            ("check_out_time", "=", False)
        ])

        active_visit = None
        checked_out_outlet_ids = []

        for visit in visits:
            if not visit.check_out_time:
                if not active_visit or visit.check_in_time > active_visit.check_in_time:
                    active_visit = visit
            else:
                checked_out_outlet_ids.append(visit.outlet_id.id)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Today's visits fetched successfully.",
            "data": {
                "active_visit": {
                    "id": active_visit.id,
                    "employee_id": active_visit.employee_id.id,
                    "outlet_id": active_visit.outlet_id.id,
                    "check_in_time": str(active_visit.check_in_time) if active_visit.check_in_time else None,
                    "visit_type": active_visit.visit_type,
                } if active_visit else None,
                "checked_out_outlet_ids": checked_out_outlet_ids
            }
        }


# -*- coding: utf-8 -*-

import math
from datetime import datetime, timezone

from odoo import http, fields
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
from odoo.addons.meta_ss_route_management.utils.routes import get_pagination


def haversine_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # radius of Earth in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


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


class MetaSSVisitController(http.Controller):

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

        date_from = payload.get("date_from") or payload.get("start_date")
        if date_from:
            domain.append(("check_in_time", ">=", "%s 00:00:00" % date_from))
        date_to = payload.get("date_to") or payload.get("end_date")
        if date_to:
            domain.append(("check_in_time", "<=", "%s 23:59:59" % date_to))

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

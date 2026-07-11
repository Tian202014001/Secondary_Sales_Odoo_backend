# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    check_mobile_model_access,
    handle_api_exception,
)

_logger = logging.getLogger(__name__)


class MetaSSLocationApiController(http.Controller):

    @http.route(f"{API_PREFIX}/employee/location/sync", type="json", auth="user", methods=["POST"])
    def sync_employee_locations(self, **payload):
        """Batch sync employee GPS location logs linked to active attendance sessions."""
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            # check_mobile_model_access(mobile_user, "sales.employee.location", "create")

            locations_data = payload.get("locations", [])
            if not locations_data:
                return {
                    "success": True,
                    "api_version": API_VERSION,
                    "message": "No coordinates to sync.",
                    "data": {"synced_count": 0, "discarded_count": 0},
                }

            employee = mobile_user.employee_id
            vals_list = []
            discarded_count = 0

            # Pre-search open or matching attendance records to minimize DB queries in loop
            for loc in locations_data:
                latitude = loc.get("latitude")
                longitude = loc.get("longitude")
                recorded_at = loc.get("recorded_at")

                if latitude is None or longitude is None or not recorded_at:
                    discarded_count += 1
                    continue

                # Query the attendance record covering the recorded timestamp
                attendance = api_env["hr.attendance"].search([
                    ("employee_id", "=", employee.id),
                    ("check_in", "<=", recorded_at),
                    "|",
                    ("check_out", ">=", recorded_at),
                    ("check_out", "=", False)
                ], limit=1)

                if not attendance:
                    discarded_count += 1
                    continue

                vals_list.append({
                    "employee_id": employee.id,
                    "attendance_id": attendance.id,
                    "latitude": float(latitude),
                    "longitude": float(longitude),
                    "recorded_at": recorded_at,
                    "is_mock": bool(loc.get("is_mock", False)),
                })

            if vals_list:
                api_env["sales.employee.location"].create(vals_list)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Location logs processed successfully.",
                "data": {
                    "synced_count": len(vals_list),
                    "discarded_count": discarded_count,
                },
            }

        except Exception as exc:
            return handle_api_exception(exc)

    @http.route(f"{API_PREFIX}/manager/my_team", type="json", auth="user", methods=["POST"])
    def get_my_team(self, **payload):
        """Get all direct and indirect subordinates with their status for a date."""
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            # check_mobile_model_access(mobile_user, "sales.employee.location", "read")

            manager_employee = mobile_user.employee_id
            subordinates = api_env["hr.employee"].sudo().search([
                ("id", "child_of", manager_employee.id),
                ("id", "!=", manager_employee.id),
                ("active", "=", True)
            ], order="name asc")

            from odoo import fields
            # Parse target date from raw request.params because get_mobile_api_context doesn't pass/sanitize date
            target_date = request.params.get("date") or fields.Date.today().strftime("%Y-%m-%d")
            date_start = f"{target_date} 00:00:00"
            date_end = f"{target_date} 23:59:59"

            my_team_data = []
            for sub in subordinates:
                last_loc = api_env["sales.employee.location"].sudo().search([
                    ("employee_id", "=", sub.id)
                ], order="recorded_at desc", limit=1)

                att = api_env["hr.attendance"].sudo().search([
                    ("employee_id", "=", sub.id),
                    ("check_in", ">=", date_start),
                    ("check_in", "<=", date_end)
                ], limit=1)

                status = "Not Checked-In"
                if att:
                    if not att.check_out:
                        status = "Active Shift"
                    else:
                        status = "Checked-Out"

                my_team_data.append({
                    "id": sub.id,
                    "name": sub.name,
                    "work_email": sub.work_email or "",
                    "avatar_url": f"/web/image/hr.employee/{sub.id}/image_128" if sub.image_128 else None,
                    "is_active_today": bool(att and not att.check_out),
                    "attendance_status": status,
                    "last_sync_time": last_loc.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if last_loc else None,
                })

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Team directory retrieved successfully.",
                "data": {
                    "my_team": my_team_data,
                }
            }

        except Exception as exc:
            return handle_api_exception(exc)

    @http.route(f"{API_PREFIX}/manager/employee/checkpoints", type="json", auth="user", methods=["POST"])
    def get_employee_checkpoints(self, **payload):
        """Get checkpoints and attendance shifts of a subordinate for a specific date."""
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            # check_mobile_model_access(mobile_user, "sales.employee.location", "read")

            manager_employee = mobile_user.employee_id
            
            # Extract from raw request.params because get_mobile_api_context overwrites employee_id in payload for security
            subordinate_id = request.params.get("employee_id")
            target_date = request.params.get("date")

            if not subordinate_id or not target_date:
                raise ValidationError("Both 'employee_id' and 'date' parameters are required.")

            subordinate = api_env["hr.employee"].sudo().search([
                ("id", "=", int(subordinate_id)),
                ("id", "child_of", manager_employee.id),
                ("id", "!=", manager_employee.id),
            ], limit=1)

            if not subordinate:
                raise AccessError("Access Denied: Employee is not in your subordinate hierarchy.")

            date_start = f"{target_date} 00:00:00"
            date_end = f"{target_date} 23:59:59"

            attendances = api_env["hr.attendance"].sudo().search([
                ("employee_id", "=", subordinate.id),
                ("check_in", ">=", date_start),
                ("check_in", "<=", date_end)
            ], order="check_in asc")

            attendances_data = []
            for att in attendances:
                points = api_env["sales.employee.location"].sudo().search([
                    ("attendance_id", "=", att.id)
                ], order="recorded_at asc")

                checkpoints_list = []
                for pt in points:
                    checkpoints_list.append({
                        "id": pt.id,
                        "latitude": pt.latitude,
                        "longitude": pt.longitude,
                        "recorded_at": pt.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if pt.recorded_at else None,
                        "is_mock": pt.is_mock
                    })

                attendances_data.append({
                    "id": att.id,
                    "check_in": att.check_in.strftime("%Y-%m-%d %H:%M:%S") if att.check_in else None,
                    "check_out": att.check_out.strftime("%Y-%m-%d %H:%M:%S") if att.check_out else None,
                    "checkpoints": checkpoints_list
                })

            barikoi_key = api_env["ir.config_parameter"].sudo().get_param("barikoi.api_key", "")
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Checkpoints retrieved successfully.",
                "data": {
                    "employee": {
                        "id": subordinate.id,
                        "name": subordinate.name
                    },
                    "date": target_date,
                    "barikoi_api_key": barikoi_key,
                    "attendances": attendances_data
                }
            }

        except Exception as exc:
            return handle_api_exception(exc)

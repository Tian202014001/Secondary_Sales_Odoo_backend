# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.exceptions import AccessError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    get_mobile_api_context,
    mobile_api_error_boundary,
    require_ui_access,
)


from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey


class MetaSSLocationApiController(http.Controller):

    @http.route(f"{API_PREFIX}/employee/location/sync", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def sync_employee_locations(self, **payload):
        """Batch sync employee GPS location logs linked to active attendance sessions."""
        mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)

        locations_data = payload.get("locations", [])
        if not locations_data:
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "No coordinates to sync.",
                "data": {"synced_count": 0, "discarded_count": 0},
            }

        employee = mobile_user.employee_id
        discarded_count = 0

        # Parse + validate every point once, tracking the covered time window.
        points = []
        for loc in locations_data:
            latitude = loc.get("latitude")
            longitude = loc.get("longitude")
            recorded_at = loc.get("recorded_at")
            if latitude is None or longitude is None or not recorded_at:
                discarded_count += 1
                continue
            try:
                recorded_dt = fields.Datetime.to_datetime(recorded_at)
            except (ValueError, TypeError):
                recorded_dt = None
            if not recorded_dt:
                discarded_count += 1
                continue
            points.append({
                "latitude": float(latitude),
                "longitude": float(longitude),
                "recorded_at": recorded_at,
                "recorded_dt": recorded_dt,
                "is_mock": bool(loc.get("is_mock", False)),
            })

        # Fetch every attendance that could cover any point in ONE query,
        # then match each point in memory (was one search per point).
        attendances = api_env["hr.attendance"]
        if points:
            min_dt = min(p["recorded_dt"] for p in points)
            max_dt = max(p["recorded_dt"] for p in points)
            attendances = api_env["hr.attendance"].search([
                ("employee_id", "=", employee.id),
                ("check_in", "<=", max_dt),
                "|",
                ("check_out", ">=", min_dt),
                ("check_out", "=", False),
            ], order="check_in")

        def _covering_attendance(recorded_dt):
            for att in attendances:
                if att.check_in and att.check_in <= recorded_dt and (
                    not att.check_out or att.check_out >= recorded_dt
                ):
                    return att
            return None

        vals_list = []
        for point in points:
            att = _covering_attendance(point["recorded_dt"])
            if not att:
                discarded_count += 1
                continue
            vals_list.append({
                "employee_id": employee.id,
                "attendance_id": att.id,
                "latitude": point["latitude"],
                "longitude": point["longitude"],
                "recorded_at": point["recorded_at"],
                "is_mock": point["is_mock"],
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

    @http.route(f"{API_PREFIX}/manager/my_team", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_my_team(self, **payload):
        """Get all direct and indirect subordinates with their status for a date."""
        mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(mobile_user, AccessKey.DASHBOARD_MODULE)

        manager_employee = mobile_user.employee_id
        subordinates = api_env["hr.employee"].sudo().search([
            ("id", "child_of", manager_employee.id),
            ("id", "!=", manager_employee.id),
            ("active", "=", True)
        ], order="name asc")

        # Parse target date from raw request.params (get_mobile_api_context doesn't pass/sanitize it).
        target_date = request.params.get("date") or fields.Date.today().strftime("%Y-%m-%d")
        date_start = f"{target_date} 00:00:00"
        date_end = f"{target_date} 23:59:59"

        sub_ids = subordinates.ids

        # ONE query for the day's attendances across all subordinates; keep the
        # earliest check-in per employee (was one search per subordinate).
        att_by_emp = {}
        if sub_ids:
            for att in api_env["hr.attendance"].sudo().search([
                ("employee_id", "in", sub_ids),
                ("check_in", ">=", date_start),
                ("check_in", "<=", date_end),
            ], order="employee_id, check_in"):
                att_by_emp.setdefault(att.employee_id.id, att)

        # ONE aggregate for the latest location timestamp per employee.
        last_sync_by_emp = {}
        if sub_ids:
            for group in api_env["sales.employee.location"].sudo().read_group(
                [("employee_id", "in", sub_ids)],
                ["recorded_at:max"],
                ["employee_id"],
            ):
                emp = group.get("employee_id")
                emp_id = emp[0] if isinstance(emp, (list, tuple)) else emp
                val = group.get("recorded_at") or group.get("recorded_at:max")
                if emp_id and val:
                    last_sync_by_emp[emp_id] = fields.Datetime.to_string(
                        fields.Datetime.to_datetime(val)
                    )

        my_team_data = []
        for sub in subordinates:
            att = att_by_emp.get(sub.id)
            if att:
                status = "Active Shift" if not att.check_out else "Checked-Out"
            else:
                status = "Not Checked-In"
            my_team_data.append({
                "id": sub.id,
                "name": sub.name,
                "work_email": sub.work_email or "",
                "avatar_url": f"/web/image/hr.employee/{sub.id}/image_128" if sub.image_128 else None,
                "is_active_today": bool(att and not att.check_out),
                "attendance_status": status,
                "last_sync_time": last_sync_by_emp.get(sub.id),
            })

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Team directory retrieved successfully.",
            "data": {
                "my_team": my_team_data,
            }
        }

    @http.route(f"{API_PREFIX}/manager/employee/checkpoints", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_employee_checkpoints(self, **payload):
        """Get checkpoints and attendance shifts of a subordinate for a specific date."""
        mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(mobile_user, AccessKey.DASHBOARD_MODULE)

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

        # ONE query for all checkpoints in the day, grouped in memory by shift
        # (was one search per attendance).
        points_by_att = {}
        if attendances:
            for pt in api_env["sales.employee.location"].sudo().search([
                ("attendance_id", "in", attendances.ids),
            ], order="recorded_at asc"):
                points_by_att.setdefault(pt.attendance_id.id, []).append(pt)

        attendances_data = []
        for att in attendances:
            checkpoints_list = [{
                "id": pt.id,
                "latitude": pt.latitude,
                "longitude": pt.longitude,
                "recorded_at": pt.recorded_at.strftime("%Y-%m-%d %H:%M:%S") if pt.recorded_at else None,
                "is_mock": pt.is_mock,
            } for pt in points_by_att.get(att.id, [])]

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

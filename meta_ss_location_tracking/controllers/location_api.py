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
)

_logger = logging.getLogger(__name__)


class MetaSSLocationApiController(http.Controller):

    @http.route(f"{API_PREFIX}/employee/location/sync", type="json", auth="user", methods=["POST"])
    def sync_employee_locations(self, **payload):
        """Batch sync employee GPS location logs linked to active attendance sessions."""
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            check_mobile_model_access(mobile_user, "sales.employee.location", "create")

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
            # Or perform a direct search per record. Since sync is batch (usually small, e.g. 10-20 points),
            # doing a quick search is clean and simple.
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
                    "accuracy": float(loc.get("accuracy")) if loc.get("accuracy") is not None else None,
                    "speed": float(loc.get("speed")) if loc.get("speed") is not None else None,
                    "battery_level": int(loc.get("battery_level")) if loc.get("battery_level") is not None else None,
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

        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            _logger.exception("sync_employee_locations failed")
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while syncing employee locations.",
            )

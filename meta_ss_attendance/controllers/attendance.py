# -*- coding: utf-8 -*-
import math
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError

try:
    from odoo.addons.meta_ss_rest_api.utils.common import (
        API_PREFIX,
        API_VERSION,
        error_response,
        get_mobile_api_context,
    )
except ImportError:
    # Fallback if meta_ss_rest_api is somehow not loaded first, though it's in depends
    API_PREFIX = "/api/v1"
    API_VERSION = "v1"
    
    def error_response(code, message, data=None):
        return {"success": False, "error": code, "message": str(message)}
        
    def get_mobile_api_context(payload):
        return request.env.user, request.env, payload


def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in meters between two points on the earth.
    
    Why Haversine?
    1. Accuracy: GPS coordinates map to a sphere. Euclidean (flat grid) math becomes 
       wildly inaccurate away from the equator. Haversine calculates the shortest path 
       over a curved surface for true accuracy.
    2. Usability: It natively outputs distance in exact meters, allowing direct 
       comparison against the `ss_attendance_radius` configuration.
    3. Lightweight: Written purely with Python's built-in `math` module, avoiding 
       heavy external dependencies like `geopy` on the Odoo server.
    4. Performance: Extremely fast execution time, crucial when looping through 
       dozens of subordinate distributors for TSM attendance checks.
    """
    if not all((lat1, lon1, lat2, lon2)):
        return float('inf')
        
    R = 6371000  # radius of Earth in meters
    phi_1 = math.radians(lat1)
    phi_2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi_1) * math.cos(phi_2) * \
        math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c


import time

_last_call_time = 0

def _reverse_geocode(lat, lon):
    global _last_call_time
    try:
        import requests
        elapsed = time.time() - _last_call_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
            
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lon}&zoom=18&addressdetails=1"
        headers = {
            # Nominatim Policy requires a valid app identifier (not a fake browser).
            # Please replace "your-email@meta.com" with a real admin email to avoid blocks.
            "User-Agent": "Secondary-Sales-Odoo-Backend/1.0 (info@metamorphosis.com.bd)",
            "Accept-Language": "en-US,en;q=0.9"
        }
        
        response = requests.get(url, headers=headers, timeout=5)
        _last_call_time = time.time()
        
        if response.status_code == 200:
            data = response.json()
            return data.get("display_name", "")
            
    except Exception as e: 
        import logging
        logging.getLogger(__name__).warning("Geocoding Error: %s", e)
        
    return ""


class AttendanceAPI(http.Controller):

    @http.route(f"{API_PREFIX}/hr/attendance/status", type="json", auth="user", methods=["POST"])
    def attendance_status(self, **payload):
        """Fetch current active attendance status."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            employee_id = payload.get("employee_id")
            if not employee_id:
                raise ValidationError("employee_id is required.")
                
            employee = api_env["hr.employee"].browse(int(employee_id))
            if not employee.exists():
                raise ValidationError("Employee not found.")

            # Get the current open attendance record
            active_attendance = api_env["hr.attendance"].search([
                ("employee_id", "=", employee.id),
                ("check_out", "=", False)
            ], limit=1)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Attendance status fetched successfully.",
                "data": {
                    "is_checked_in": bool(active_attendance),
                    "active_id": active_attendance.id if active_attendance else None,
                    "active_check_in": active_attendance.check_in.strftime("%Y-%m-%d %H:%M:%S") if active_attendance else None,
                    "check_in_address": (active_attendance.check_in_address or "") if active_attendance else "",
                }
            }
        except Exception as e:
            request.env.cr.rollback()
            return error_response(400, str(e))

    @http.route(f"{API_PREFIX}/hr/attendance/history", type="json", auth="user", methods=["POST"])
    def attendance_history(self, **payload):
        """Fetch paginated attendance logs for the employee."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            employee_id = payload.get("employee_id")
            if not employee_id:
                raise ValidationError("employee_id is required.")
                
            employee = api_env["hr.employee"].browse(int(employee_id))
            if not employee.exists():
                raise ValidationError("Employee not found.")

            # Pagination for history
            page = int(payload.get("page", 1))
            page_size = int(payload.get("page_size", 20))
            offset = (page - 1) * page_size

            history = api_env["hr.attendance"].search([
                ("employee_id", "=", employee.id)
            ], order="check_in desc", limit=page_size, offset=offset)
            
            total = api_env["hr.attendance"].search_count([("employee_id", "=", employee.id)])

            logs = []
            for rec in history:
                logs.append({
                    "id": rec.id,
                    "date": rec.check_in.strftime("%Y-%m-%d") if rec.check_in else None,
                    "check_in": rec.check_in.strftime("%Y-%m-%d %H:%M:%S") if rec.check_in else None,
                    "check_out": rec.check_out.strftime("%Y-%m-%d %H:%M:%S") if rec.check_out else "",
                    "worked_hours": round(rec.worked_hours, 2) if rec.worked_hours else 0.0,
                    "distributor_name": rec.ss_distributor_id.name if rec.ss_distributor_id else "",
                    "check_in_address": rec.check_in_address or "",
                    "check_out_address": rec.check_out_address or "",
                })

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Attendance history fetched successfully.",
                "data": logs,
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total
                }
            }
        except Exception as e:
            request.env.cr.rollback()
            return error_response(400, str(e))

    @http.route(f"{API_PREFIX}/hr/attendance/action", type="json", auth="user", methods=["POST"])
    def attendance_action(self, **payload):
        """Handle check_in and check_out with strict Geo-fencing."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            employee_id = payload.get("employee_id")
            action = payload.get("action")
            lat = payload.get("latitude")
            lon = payload.get("longitude")
            address = payload.get("address") # Optionally from payload

            if not all((employee_id, action, lat, lon)):
                raise ValidationError("employee_id, action (check_in/check_out), latitude, and longitude are required.")
                
            try:
                lat = float(lat)
                lon = float(lon)
            except ValueError:
                raise ValidationError("Invalid coordinates format.")

            if not address:
                address = _reverse_geocode(lat, lon)

            employee = api_env["hr.employee"].browse(int(employee_id))
            if not employee.exists():
                raise ValidationError("Employee not found.")

            # 1. Update Employee Contact Location
            if employee.work_contact_id:
                employee.work_contact_id.sudo().write({
                    "partner_latitude": lat,
                    "partner_longitude": lon
                })

            # 2. Geo-Fence Validation
            skip_geolocation = employee.mobile_user_group_id and employee.mobile_user_group_id.skip_attendance_geolocation

            subordinates = api_env["hr.employee"].sudo().search([("id", "child_of", employee.id)])
            allowed_distributors = subordinates.mapped("distributor_contact_ids")
            
            if not skip_geolocation and not allowed_distributors:
                raise ValidationError("No distributors assigned. You cannot punch attendance without an assigned distributor.")

            is_valid_location = False
            valid_distributor = None
            
            if skip_geolocation:
                is_valid_location = True
                valid_distributor = allowed_distributors[0] if allowed_distributors else None
            else:
                for distributor in allowed_distributors:
                    d_lat = distributor.partner_latitude
                    d_lon = distributor.partner_longitude
                    radius = distributor.ss_attendance_radius or 50.0  # fallback if field is 0
                    
                    if d_lat and d_lon:
                        distance = haversine_distance(lat, lon, d_lat, d_lon)
                        if distance <= radius:
                            is_valid_location = True
                            valid_distributor = distributor
                            break

                if not is_valid_location:
                    raise ValidationError("You must be within the assigned distributor's radius to check in/out.")

            # 3. Create or Update Attendance Record
            attendance_obj = api_env["hr.attendance"]
            
            if action == "check_in":
                # Ensure not already checked in
                open_rec = attendance_obj.search([
                    ("employee_id", "=", employee.id),
                    ("check_out", "=", False)
                ], limit=1)
                
                if open_rec:
                    raise ValidationError("You are already checked in.")
                    
                new_rec = attendance_obj.create({
                    "employee_id": employee.id,
                    "check_in": fields.Datetime.now(),
                    "check_in_latitude": lat,
                    "check_in_longitude": lon,
                    "check_in_address": address,
                    "ss_distributor_id": valid_distributor.id if valid_distributor else False,
                })
                
                return {
                    "success": True,
                    "api_version": API_VERSION,
                    "message": "Checked in successfully.",
                    "data": {
                        "id": new_rec.id,
                        "check_in": new_rec.check_in.strftime("%Y-%m-%d %H:%M:%S"),
                        "check_in_address": address or "",
                    }
                }
                
            elif action == "check_out":
                open_rec = attendance_obj.search([
                    ("employee_id", "=", employee.id),
                    ("check_out", "=", False)
                ], limit=1)
                
                if not open_rec:
                    raise ValidationError("You are not currently checked in.")
                    
                open_rec.write({
                    "check_out": fields.Datetime.now(),
                    "check_out_latitude": lat,
                    "check_out_longitude": lon,
                    "check_out_address": address or "",
                })
                
                return {
                    "success": True,
                    "api_version": API_VERSION,
                    "message": "Checked out successfully.",
                    "data": {
                        "id": open_rec.id,
                        "check_out": open_rec.check_out.strftime("%Y-%m-%d %H:%M:%S"),
                        "worked_hours": round(open_rec.worked_hours, 2) if open_rec.worked_hours else 0.0,
                        "check_out_address": address or "",
                    }
                }
            else:
                raise ValidationError("Invalid action. Must be 'check_in' or 'check_out'.")

        except Exception as e:
            request.env.cr.rollback()
            return error_response(400, str(e))

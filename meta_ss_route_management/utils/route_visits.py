# -*- coding: utf-8 -*-

from datetime import datetime
from odoo import fields
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.addons.meta_ss_rest_api.utils.common import format_date

def serialize_route_visit_summary(visit):
    """Serialize basic route visit info for history lists"""
    return {
        "visit_id": visit.id,
        "route_id": visit.route_id.id,
        "route_name": visit.route_id.name,
        "visit_date": format_date(visit.visit_date),
        "state": visit.state,
        "start_time": visit.start_time.strftime(DEFAULT_SERVER_DATETIME_FORMAT) if visit.start_time else None,
        "end_time": visit.end_time.strftime(DEFAULT_SERVER_DATETIME_FORMAT) if visit.end_time else None,
    }

def serialize_route_visit_line(line):
    """Serialize a single visit line (outlet check-in)"""
    return {
        "line_id": line.id,
        "outlet_id": line.outlet_id.id,
        "outlet_name": line.outlet_id.name,
        "state": line.state,
        "note": line.note,
        "check_in_time": line.check_in_time.strftime(DEFAULT_SERVER_DATETIME_FORMAT) if line.check_in_time else None,
        "check_in_latitude": line.check_in_latitude,
        "check_in_longitude": line.check_in_longitude,
        "check_out_time": line.check_out_time.strftime(DEFAULT_SERVER_DATETIME_FORMAT) if line.check_out_time else None,
        "check_out_latitude": line.check_out_latitude,
        "check_out_longitude": line.check_out_longitude,
    }

def serialize_route_visit_details(visit):
    """Serialize full route visit including lines"""
    data = serialize_route_visit_summary(visit)
    data["visit_lines"] = [serialize_route_visit_line(line) for line in visit.visit_line_ids]
    return data

def perform_route_visit_action(env, visit_id, payload):
    """Handle state changes (check-in, check-out, skip, complete) for a route visit"""
    visit = env["sale.route.visit"].browse(visit_id)
    if not visit.exists():
        return {"error": "Route visit not found"}
        
    action = payload.get("action")
    if not action:
        return {"error": "Action is required"}

    # Complete Visit
    if action == "complete":
        try:
            visit.action_done()
            return {"success": True, "state": visit.state}
        except Exception as e:
            return {"error": str(e)}

    # Check-In
    if action == "check_in":
        outlet_id = payload.get("outlet_id")
        if not outlet_id:
            return {"error": "outlet_id is required for check-in"}
        
        # Check if they are already checked into this outlet on this visit
        existing_line = env["sale.route.visit.line"].search([
            ("visit_id", "=", visit.id),
            ("outlet_id", "=", outlet_id),
        ], limit=1)
        
        if existing_line:
            if existing_line.state == "checked_in":
                return {"error": "Already checked in at this outlet"}
            if existing_line.state == "checked_out":
                return {"error": "Already completed visit at this outlet"}

        # Create the new checked-in line
        try:
            new_line = env["sale.route.visit.line"].create({
                "visit_id": visit.id,
                "outlet_id": outlet_id,
                "state": "checked_in",
                "check_in_time": fields.Datetime.now(),
                "check_in_latitude": payload.get("latitude", 0.0),
                "check_in_longitude": payload.get("longitude", 0.0),
            })
            return {"success": True, "line_id": new_line.id, "state": "checked_in"}
        except Exception as e:
            return {"error": str(e)}

    # Check-Out
    if action == "check_out":
        line_id = payload.get("line_id")
        if not line_id:
            return {"error": "line_id is required for check-out"}
            
        line = env["sale.route.visit.line"].browse(line_id)
        if not line.exists() or line.visit_id.id != visit.id:
            return {"error": "Visit line not found"}
            
        try:
            line.write({
                "state": "checked_out",
                "check_out_time": fields.Datetime.now(),
                "check_out_latitude": payload.get("latitude", 0.0),
                "check_out_longitude": payload.get("longitude", 0.0),
            })
            return {"success": True, "state": "checked_out"}
        except Exception as e:
            return {"error": str(e)}

    # Skip
    if action == "skip":
        outlet_id = payload.get("outlet_id")
        note = payload.get("note", "")
        if not outlet_id:
            return {"error": "outlet_id is required to skip"}
            
        try:
            new_line = env["sale.route.visit.line"].create({
                "visit_id": visit.id,
                "outlet_id": outlet_id,
                "state": "skipped",
                "note": note
            })
            return {"success": True, "line_id": new_line.id, "state": "skipped"}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown action: {action}"}

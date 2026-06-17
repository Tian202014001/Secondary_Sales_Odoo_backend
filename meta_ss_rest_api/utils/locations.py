# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.osv import expression

from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination, parse_active_filter


def build_location_domain(env, payload):
    """Build a search domain for standard stock locations based on API payload."""
    domain = [
        ("active", "=", parse_active_filter(payload)),
        ("company_id", "in", [False, env.company.id]),
    ]

    # Filter by usage(s)
    usage = payload.get("usage")
    if usage:
        if isinstance(usage, list):
            domain = expression.AND([domain, [("usage", "in", usage)]])
        else:
            domain = expression.AND([domain, [("usage", "=", str(usage).strip())]])

    # Filter by secondary sales location type(s)
    ss_location_type = payload.get("ss_location_type")
    if ss_location_type:
        if isinstance(ss_location_type, list):
            domain = expression.AND([domain, [("ss_location_type", "in", ss_location_type)]])
        else:
            domain = expression.AND([domain, [("ss_location_type", "=", str(ss_location_type).strip())]])

    # Filter by assigned employee
    employee_id = payload.get("employee_id") or payload.get("ss_employee_id")
    if employee_id:
        try:
            employee_id = int(employee_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'employee_id' must be a valid integer id.") from exc
        domain = expression.AND([domain, [("ss_employee_id", "child_of", employee_id)]])

    # Filter by assigned distributor
    distributor_id = payload.get("distributor_id") or payload.get("ss_distributor_id")
    if distributor_id:
        try:
            distributor_id = int(distributor_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'distributor_id' must be a valid integer id.") from exc
        domain = expression.AND([domain, [("ss_distributor_id", "=", distributor_id)]])

    # Search term filter
    search = (payload.get("search") or "").strip()
    if search:
        domain = expression.AND([
            domain,
            expression.OR([
                [("name", "ilike", search)],
                [("complete_name", "ilike", search)],
            ]),
        ])

    return domain


def serialize_location(location):
    """Serialize a stock.location record into a JSON-compatible dict."""
    return {
        "id": location.id,
        "name": location.name,
        "complete_name": location.complete_name,
        "display_name": location.display_name,
        "usage": location.usage,
        "active": location.active,
        "ss_location_type": location.ss_location_type,
        "employee": {
            "id": location.ss_employee_id.id,
            "name": location.ss_employee_id.name,
        } if location.ss_employee_id else None,
        "distributor": {
            "id": location.ss_distributor_id.id,
            "name": location.ss_distributor_id.name,
        } if location.ss_distributor_id else None,
    }


def get_location_pagination(payload):
    """Get standard pagination parameters for location queries."""
    return get_pagination(payload)

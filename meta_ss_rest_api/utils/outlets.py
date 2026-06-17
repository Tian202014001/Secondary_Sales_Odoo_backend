# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.osv import expression

from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination, parse_active_filter


def parse_assigned_filter(payload):
    """Return a tri-state assignment filter from API payload."""
    if "assigned" not in payload:
        return None

    assigned = payload.get("assigned")
    if assigned in (None, "", "all"):
        return None
    if isinstance(assigned, bool):
        return assigned
    if isinstance(assigned, str):
        return assigned.strip().lower() not in ("0", "false", "no")

    return bool(assigned)


def get_employee_route(env, employee, route_id):
    """Return a route assigned to the employee or raise a validation error."""
    try:
        route_id = int(route_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'route_id' must be a valid integer id.") from exc

    route = env["sale.route"].sudo().search([
        ("id", "=", route_id),
        ("active", "=", True),
        ("ss_employee_id", "child_of", employee.id),
    ], limit=1)
    if not route:
        raise ValidationError("No active route was found for the provided route and employee.")

    return route


def build_employee_outlet_domain(env, employee, payload):
    """Build outlet search domain scoped to routes visible to one employee."""
    domain = [
        ("customer_type", "=", "outlet"),
        ("active", "=", parse_active_filter(payload)),
    ]

    route = None
    route_id = payload.get("route_id")
    if route_id:
        route = get_employee_route(env, employee, route_id)

    employee_routes = env["sale.route"].sudo().search([
        ("active", "=", True),
        ("ss_employee_id", "child_of", employee.id),
    ])
    assigned = parse_assigned_filter(payload)

    if route and assigned is True:
        visibility_domain = [("outlet_route_id", "=", route.id)]
    elif route and assigned is False:
        visibility_domain = [("outlet_route_id", "=", False)]
    elif route:
        visibility_domain = [
            "|",
            ("outlet_route_id", "=", False),
            ("outlet_route_id", "=", route.id),
        ]
    elif assigned is True:
        visibility_domain = [("outlet_route_id", "in", employee_routes.ids)]
    elif assigned is False:
        visibility_domain = [("outlet_route_id", "=", False)]
    else:
        visibility_domain = [("outlet_route_id", "in", employee_routes.ids)]

    domain = expression.AND([domain, visibility_domain])

    search = (payload.get("search") or "").strip()
    if search:
        search_domain = expression.OR([
            [("name", "ilike", search)],
            [("phone", "ilike", search)],
            [("mobile", "ilike", search)],
            [("email", "ilike", search)],
            [("ref", "ilike", search)],
        ])
        domain = expression.AND([domain, search_domain])

    return domain


def serialize_outlets(outlets):
    """Serialize res.partner outlet records for API response."""
    data = []
    for outlet in outlets:
        data.append({
            "id": outlet.id,
            "name": outlet.name,
            "phone": outlet.phone or None,
            "mobile": outlet.mobile or None,
            "email": outlet.email or None,
            "street": outlet.street or None,
            "street2": outlet.street2 or None,
            "city": outlet.city or None,
            "zip": outlet.zip or None,
            "vat": outlet.vat or None,
            "active": outlet.active,
            "assigned_route": {
                "id": outlet.outlet_route_id.id,
                "name": outlet.outlet_route_id.name,
                "code": outlet.outlet_route_id.code or None,
            } if outlet.outlet_route_id else None,
        })
    return data


def get_outlet_pagination(payload):
    """Return pagination values for outlet list APIs."""
    return get_pagination(payload)

# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.addons.meta_ss_rest_api.utils.helpers import _get_employee


ROUTE_WRITE_FIELDS = (
    "name",
    "code",
    "active",
    "distributor_id",
    "employee_ids",
    "outlets",
)

OUTLET_CREATE_FIELDS = (
    "name",
    "phone",
    "mobile",
    "email",
    "street",
    "street2",
    "city",
    "zip",
    "vat",
    "comment",
)


def get_pagination(payload):
    """Return pagination values from API payload."""
    try:
        page = int(payload.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(payload.get("page_size", 20))
    except (TypeError, ValueError):
        page_size = 20

    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)
    limit = page_size
    offset = (page - 1) * page_size
    return limit, offset, page, page_size


def parse_active_filter(payload):
    """Return a boolean active filter value from common API payload formats."""
    active = payload.get("active", True)
    if isinstance(active, bool):
        return active
    if isinstance(active, str):
        return active.strip().lower() not in ("0", "false", "no")
    return bool(active)


def build_employee_route_domain(employee, payload):
    """Build route search domain scoped to one employee."""
    domain = [
        ("active", "=", parse_active_filter(payload)),
        ("ss_employee_ids", "in", [employee.id]),
    ]

    search = (payload.get("search") or "").strip()
    if search:
        domain += [
            "|",
            ("name", "ilike", search),
            ("code", "ilike", search),
        ]

    distributor_id = payload.get("distributor_id")
    if distributor_id:
        try:
            distributor_id = int(distributor_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'distributor_id' must be a valid integer id.") from exc
        domain.append(("distributor_contact_id", "=", distributor_id))

    route_id = payload.get("route_id")
    if route_id:
        try:
            route_id = int(route_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'route_id' must be a valid integer id.") from exc
        domain.append(("id", "=", route_id))

    return domain


def has_route_create_payload(payload):
    """Return whether the route list endpoint payload should create a route."""
    return bool(payload.get("name"))


def has_route_update_payload(payload):
    """Return whether the route detail endpoint payload should update a route."""
    return any(field in payload for field in ROUTE_WRITE_FIELDS)


def prepare_route_values(env, payload, employee, create=False):
    """Build validated sale.route values from an API payload."""
    values = {}

    if create:
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValidationError("'name' is required.")
        values["name"] = name
    elif "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValidationError("'name' cannot be empty.")
        values["name"] = name

    if "code" in payload:
        code = (payload.get("code") or "").strip()
        values["code"] = code or False

    if "active" in payload:
        values["active"] = parse_active_filter(payload)

    if "distributor_id" in payload:
        distributor_id = payload.get("distributor_id")
        values["distributor_contact_id"] = _validate_partner(
            env,
            distributor_id,
            "distributor",
            "distributor_id",
        ).id if distributor_id else False

    if create or "employee_ids" in payload:
        values["ss_employee_ids"] = [(6, 0, _get_employee_ids(env, payload, employee))]

    if "outlets" in payload:
        values["route_line_ids"] = _get_route_line_commands(
            env,
            payload.get("outlets") or [],
            replace_existing=not create,
        )

    return values


def prepare_route_outlet_line_values(env, payload):
    """Build validated sale.route.line values from an API payload."""
    outlet_partner = _get_or_create_outlet_partner(env, payload)

    try:
        sequence = int(payload.get("sequence", 10))
        expected_visit_time = float(payload.get("expected_visit_time", 0.0))
    except (TypeError, ValueError) as exc:
        raise ValidationError("'sequence' and 'expected_visit_time' must be numeric.") from exc

    return {
        "outlet_id": outlet_partner.id,
        "sequence": sequence,
        "expected_visit_time": expected_visit_time,
        "active": parse_active_filter(payload),
    }


def _get_employee_ids(env, payload, current_employee):
    """Return validated employee ids, always keeping the requesting employee assigned."""
    employee_ids = payload.get("employee_ids") or [current_employee.id]
    if not isinstance(employee_ids, list):
        raise ValidationError("'employee_ids' must be a list of employee ids.")

    try:
        employee_ids = [int(employee_id) for employee_id in employee_ids]
    except (TypeError, ValueError) as exc:
        raise ValidationError("'employee_ids' must contain valid integer ids.") from exc
    if current_employee.id not in employee_ids:
        employee_ids.append(current_employee.id)

    employees = env["hr.employee"].sudo().browse(employee_ids).exists()
    if len(employees) != len(set(employee_ids)):
        raise ValidationError("One or more employee ids are invalid.")

    return list(dict.fromkeys(employee_ids))


def _get_route_line_commands(env, outlets, replace_existing=True):
    """Return one2many commands for route outlet lines from API payload."""
    if not isinstance(outlets, list):
        raise ValidationError("'outlets' must be a list.")

    commands = [(5, 0, 0)] if replace_existing else []
    seen_outlet_ids = set()
    for index, outlet in enumerate(outlets, start=1):
        outlet_payload = outlet if isinstance(outlet, dict) else {"outlet_id": outlet}
        outlet_partner = _get_or_create_outlet_partner(env, outlet_payload)
        if outlet_partner.id in seen_outlet_ids:
            raise ValidationError("Duplicate outlet ids are not allowed in one route.")
        seen_outlet_ids.add(outlet_partner.id)

        try:
            sequence = int(outlet_payload.get("sequence", index * 10))
            expected_visit_time = float(outlet_payload.get("expected_visit_time", 0.0))
        except (TypeError, ValueError) as exc:
            raise ValidationError("'sequence' and 'expected_visit_time' must be numeric.") from exc

        commands.append((0, 0, {
            "outlet_id": outlet_partner.id,
            "sequence": sequence,
            "expected_visit_time": expected_visit_time,
            "active": parse_active_filter(outlet_payload),
        }))

    return commands


def _get_or_create_outlet_partner(env, outlet_payload):
    """Return an existing outlet or create a new outlet from a route line payload."""
    outlet_id = outlet_payload.get("outlet_id") or outlet_payload.get("id")
    if outlet_id:
        return _validate_partner(env, outlet_id, "outlet", "outlet_id")

    return _create_outlet_partner(env, outlet_payload)


def _create_outlet_partner(env, outlet_payload):
    """Create an outlet contact from a route line payload."""
    name = (outlet_payload.get("name") or outlet_payload.get("outlet_name") or "").strip()
    if not name:
        raise ValidationError("'outlet_id' or outlet 'name' is required.")

    values = {
        "name": name,
        "customer_type": "outlet",
    }
    for field_name in OUTLET_CREATE_FIELDS:
        if field_name == "name" or field_name not in outlet_payload:
            continue
        values[field_name] = outlet_payload.get(field_name) or False

    return env["res.partner"].sudo().create(values)


def _validate_partner(env, partner_id, customer_type, field_name):
    """Return a validated partner record for a required customer type."""
    if not partner_id:
        raise ValidationError("'%s' is required." % field_name)

    try:
        partner_id = int(partner_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'%s' must be a valid integer id." % field_name) from exc

    partner = env["res.partner"].sudo().browse(partner_id).exists()
    if not partner:
        raise ValidationError("No partner was found for '%s'." % field_name)
    if partner.customer_type != customer_type:
        raise ValidationError("'%s' must be a %s contact." % (field_name, customer_type))

    return partner


def serialize_routes(routes):
    """Serialize sale.route records for API response."""
    data = []
    for route in routes:
        data.append({
            "id": route.id,
            "name": route.name,
            "code": route.code or None,
            "active": route.active,
            "distributor": {
                "id": route.distributor_contact_id.id,
                "name": route.distributor_contact_id.name,
            } if route.distributor_contact_id else None,
            "employees": [
                {
                    "id": employee.id,
                    "name": employee.name,
                }
                for employee in route.ss_employee_ids
            ],
            "outlet_count": route.env["sale.route.line"].search_count([("route_id", "=", route.id), ("active", "=", True)]),
        })
    return data


def serialize_route_outlet_line(route_line):
    """Serialize one sale.route.line record for API response."""
    return {
        "line_id": route_line.id,
        "id": route_line.outlet_id.id,
        "name": route_line.outlet_id.name,
        "sequence": route_line.sequence,
        "expected_visit_time": route_line.expected_visit_time,
        "phone": route_line.outlet_id.phone or None,
        "mobile": route_line.outlet_id.mobile or None,
        "email": route_line.outlet_id.email or None,
        "street": route_line.outlet_id.street or None,
        "street2": route_line.outlet_id.street2 or None,
        "city": route_line.outlet_id.city or None,
        "zip": route_line.outlet_id.zip or None,
        "vat": route_line.outlet_id.vat or None,
        "active": route_line.active,
    }


def serialize_route_detail(route):
    """Serialize one sale.route record with its ordered outlet list."""
    return {
        "id": route.id,
        "name": route.name,
        "code": route.code or None,
        "active": route.active,
        "distributor": {
            "id": route.distributor_contact_id.id,
            "name": route.distributor_contact_id.name,
            "phone": route.distributor_contact_id.phone or None,
            "mobile": route.distributor_contact_id.mobile or None,
            "email": route.distributor_contact_id.email or None,
        } if route.distributor_contact_id else None,
        "employees": [
            {
                "id": employee.id,
                "name": employee.name,
                "work_phone": employee.work_phone or None,
                "work_email": employee.work_email or None,
            }
            for employee in route.ss_employee_ids
        ],
        "outlets": [
            serialize_route_outlet_line(route_line)
            for route_line in route.route_line_ids.sorted(lambda line: (line.sequence, line.id))
        ],
        "outlet_count": len(route.route_line_ids.filtered("active")),
    }

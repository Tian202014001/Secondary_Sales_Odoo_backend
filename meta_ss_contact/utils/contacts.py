# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.addons.meta_ss_rest_api.utils.helpers import _get_employee, _get_integer_id
from odoo.addons.meta_ss_rest_api.utils.mobile_policy import MobilePolicy
from odoo.osv import expression

from odoo.addons.meta_ss_rest_api.utils.outlets import (
    build_employee_outlet_domain,
    parse_assigned_filter,
)
from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination, parse_active_filter


CONTACT_TYPES = ("distributor", "outlet")
CONTACT_CREATE_FIELDS = (
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
    "partner_latitude",
    "partner_longitude",
)


def normalize_customer_type(payload, customer_type=None, required=True):
    """Return a supported contact customer_type from route arg or payload."""
    customer_type = customer_type or payload.get("customer_type") or payload.get("type")
    if not customer_type:
        if required:
            raise ValidationError("'customer_type' is required.")
        return None

    customer_type = str(customer_type).strip().lower()
    if customer_type not in CONTACT_TYPES:
        raise ValidationError(
            "'customer_type' must be one of: %s." % ", ".join(CONTACT_TYPES)
        )
    return customer_type


def build_contact_domain(env, payload, customer_type=None):
    """Build a res.partner search domain for the unified contact API."""
    customer_type = normalize_customer_type(payload, customer_type, required=False)
    if (
        customer_type == "outlet"
        and payload.get("employee_id")
    ):
        employee = _get_employee(env, payload.get("employee_id"))
        return build_employee_outlet_domain(env, employee, payload)

    domain = [
        ("active", "=", parse_active_filter(payload)),
    ]
    if customer_type:
        domain.append(("customer_type", "=", customer_type))

    if customer_type == "distributor" and payload.get("employee_id"):
        employee = _get_employee(env, payload.get("employee_id"))
        distributor_ids = MobilePolicy.visible_distributor_ids(env, employee)
        if distributor_ids:
            domain.append(("id", "in", distributor_ids))
        else:
            domain.append(("id", "=", 0))

    distributor_id = payload.get("distributor_id")
    if distributor_id:
        distributor_id = _get_integer_id(distributor_id, "distributor_id")
        domain = expression.AND([
            domain,
            expression.OR([
                [("id", "=", distributor_id)],
                [("outlet_route_id.distributor_contact_id", "=", distributor_id)],
            ]),
        ])

    route_id = payload.get("route_id")
    if route_id:
        domain.append(("outlet_route_id", "=", _get_integer_id(route_id, "route_id")))

    if customer_type == "outlet":
        assigned = parse_assigned_filter(payload)
        if assigned is True:
            domain.append(("outlet_route_id", "!=", False))
        elif assigned is False:
            domain.append(("outlet_route_id", "=", False))

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


def get_contact_for_payload(env, contact_id, payload, customer_type=None):
    """Return one contact through the same visibility domain as the list API."""
    customer_type = normalize_customer_type(payload, customer_type, required=False)
    domain = build_contact_domain(env, payload, customer_type)
    domain = expression.AND([domain, [("id", "=", _get_integer_id(contact_id, "contact_id"))]])
    contact = env["res.partner"].sudo().search(domain, limit=1)
    if not contact:
        raise ValidationError("No contact was found for the provided id.")
    return contact


def build_contact_order_history_domain(contact, payload):
    """Build a sale order history domain scoped to the requested outlet/contact."""
    domain = [
        ("partner_id", "=", contact.id),
        ("state", "in", ["sale", "done"]),
    ]
    employee_id = payload.get("employee_id")
    if employee_id:
        domain.append(("so_employee_id", "child_of", _get_integer_id(employee_id, "employee_id")))
    return domain


def build_contact_visit_history_domain(contact, payload):
    """Build an outlet visit history domain scoped to the requested outlet/contact."""
    domain = [("outlet_id", "=", contact.id)]
    employee_id = payload.get("employee_id")
    if employee_id:
        domain.append(("employee_id", "child_of", _get_integer_id(employee_id, "employee_id")))
    return domain


def prepare_contact_values(payload, customer_type):
    """Build validated res.partner values for distributor or outlet creation."""
    customer_type = normalize_customer_type(payload, customer_type)
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValidationError("'name' is required.")

    values = {
        "name": name,
        "customer_type": customer_type,
    }
    for field_name in CONTACT_CREATE_FIELDS:
        if field_name == "name" or field_name not in payload:
            continue
        values[field_name] = payload.get(field_name) or False

    route_id = payload.get("route_id") or payload.get("outlet_route_id")
    if route_id:
        if customer_type != "outlet":
            raise ValidationError("'route_id' can only be used for outlet contacts.")
        values["outlet_route_id"] = _get_integer_id(route_id, "route_id")

    return values


def prepare_contact_update_values(payload, customer_type):
    """Build validated res.partner values for distributor or outlet update."""
    customer_type = normalize_customer_type(payload, customer_type)
    values = {}
    for field_name in CONTACT_CREATE_FIELDS:
        if field_name in payload:
            values[field_name] = payload.get(field_name) or False

    route_id = payload.get("route_id") or payload.get("outlet_route_id")
    if route_id:
        if customer_type != "outlet":
            raise ValidationError("'route_id' can only be used for outlet contacts.")
        values["outlet_route_id"] = _get_integer_id(route_id, "route_id")

    return values


def ensure_distributor_locations(env, distributor):
    """Delegate to model method to ensure stock locations exist."""
    return distributor._ensure_distributor_locations()


def _find_or_create_location(StockLocation, name, usage, parent_id, scrap_location=False):
    """Find an existing stock location or create it, then force complete_name recompute."""
    loc = StockLocation.search([
        ("name", "=", name),
        ("usage", "=", usage),
        ("location_id", "=", parent_id),
        ("active", "=", True),
    ], limit=1)
    if not loc:
        vals = {
            "name": name,
            "usage": usage,
            "location_id": parent_id,
        }
        if scrap_location:
            vals["scrap_location"] = True
        loc = StockLocation.create(vals)
        loc._compute_complete_name()
        loc.flush_recordset(["complete_name"])
    return loc




def serialize_contacts(contacts):
    """Serialize distributor or outlet partner records for API response."""
    data = []
    for contact in contacts:
        contact = contact.sudo()
        cust_loc = contact.property_stock_customer.sudo() if contact.property_stock_customer else None
        scrap_loc = contact.scrap_location_id.sudo() if contact.scrap_location_id else None
        data.append({
            "id": contact.id,
            "name": contact.name,
            "customer_type": contact.customer_type,
            "phone": contact.phone or None,
            "mobile": contact.mobile or None,
            "email": contact.email or None,
            "street": contact.street or None,
            "street2": contact.street2 or None,
            "city": contact.city or None,
            "zip": contact.zip or None,
            "vat": contact.vat or None,
            "partner_latitude": contact.partner_latitude,
            "partner_longitude": contact.partner_longitude,
            "active": contact.active,
            "customer_stock_location": {
                "id": cust_loc.id,
                "name": cust_loc.name,
                "display_name": cust_loc.display_name,
                "usage": cust_loc.usage,
            } if cust_loc else None,
            "scrap_location": {
                "id": scrap_loc.id,
                "name": scrap_loc.name,
                "display_name": scrap_loc.display_name,
            } if scrap_loc else None,
        })
    return data


def get_contact_pagination(payload):
    """Return pagination values for contact list APIs."""
    return get_pagination(payload)

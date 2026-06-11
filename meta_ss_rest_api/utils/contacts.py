# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.addons.meta_ss_rest_api.utils.helpers import _get_employee, _get_integer_id
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
    """Create and assign stock locations for a distributor.

    Resulting hierarchy:
        Partners/Customers/          (Odoo default)
          <dealer name>/             (customer)
            Stock                    (customer) → property_stock_customer
            Scrap                    (customer, scrap=True) → scrap_location_id
    """
    if distributor.customer_type != "distributor":
        return False

    StockLocation = env["stock.location"].sudo()

    # ── 1. Shared "Partners/Customers" root (Odoo default) ────────────────────
    customer_parent = env.ref("stock.stock_location_customers")

    # ── 2. Dealer folder: Partners/Customers/<dealer name>/ ───────────────────
    dealer_folder = _find_or_create_location(
        StockLocation, distributor.name, "customer", customer_parent.id
    )

    # ── 3. Stock child → property_stock_customer ──────────────────────────────
    if (
        not distributor.property_stock_customer
        or distributor.property_stock_customer == customer_parent
    ):
        stock_loc = _find_or_create_location(StockLocation, "Stock", "customer", dealer_folder.id)
        distributor.sudo().property_stock_customer = stock_loc

    # ── 4. Scrap child → scrap_location_id ───────────────────────────────────
    has_scrap_field = "scrap_location_id" in distributor._fields
    if has_scrap_field and not distributor.scrap_location_id:
        scrap_loc = _find_or_create_location(
            StockLocation, "Scrap", "customer", dealer_folder.id, scrap_location=True
        )
        distributor.sudo().scrap_location_id = scrap_loc

    return True


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
        cust_loc = contact.property_stock_customer
        scrap_loc = contact.scrap_location_id
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



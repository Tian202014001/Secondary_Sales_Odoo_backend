# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.addons.meta_ss_rest_api.utils.helpers import _get_employee
from odoo.osv import expression

from odoo.addons.meta_ss_contact.utils.contacts import ensure_distributor_locations
from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination


def build_virtual_location_domain(env, payload):
    location_type = (payload.get("location_type") or "van_loading").strip()
    if location_type != "van_loading":
        raise ValidationError("Unsupported virtual location type.")

    domain = [
        ("ss_location_type", "=", location_type),
        ("company_id", "in", [False, env.company.id]),
    ]

    distributor_id = payload.get("distributor_id")
    if distributor_id:
        try:
            distributor_id = int(distributor_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'distributor_id' must be a valid integer id.") from exc
        domain = expression.AND([domain, [("ss_distributor_id", "=", distributor_id)]])
    elif payload.get("employee_id"):
        employee = _get_employee(env, payload.get("employee_id"))
        if employee.distributor_contact_id:
            domain = expression.AND([
                domain,
                [("ss_distributor_id", "=", employee.distributor_contact_id.id)],
            ])

    assigned_employee_id = payload.get("assigned_employee_id")
    if assigned_employee_id:
        assigned_employee = _get_employee(env, assigned_employee_id)
        domain = expression.AND([domain, [("ss_employee_id", "=", assigned_employee.id)]])

    search = (payload.get("search") or "").strip()
    if search:
        domain = expression.AND([
            domain,
            [("name", "ilike", search)],
        ])
    return domain


def serialize_virtual_location(location):
    """Serialize a van-loading stock location with its paired scrap sibling."""
    scrap_sibling = _get_scrap_sibling(location)
    return {
        "id": location.id,
        "name": location.name,
        "complete_name": location.complete_name,
        "usage": location.usage,
        "location_type": location.ss_location_type,
        "scrap_location": {
            "id": scrap_sibling.id,
            "name": scrap_sibling.name,
            "complete_name": scrap_sibling.complete_name,
        } if scrap_sibling else None,
        "employee": {
            "id": location.ss_employee_id.id,
            "name": location.ss_employee_id.name,
        } if location.ss_employee_id else None,
        "distributor": {
            "id": location.ss_distributor_id.id,
            "name": location.ss_distributor_id.name,
        } if location.ss_distributor_id else None,
    }


def prepare_virtual_location_vals(env, payload):
    """Build vals for a van-loading location.

    Resulting location tree:
        Partners/
          <Dealer>/                     (view, dealer folder)
            Stock/                      (view = dealer's property_stock_customer)
              <van name> - Stock        ← this location (van_loading)
              <van name> - Scrap        ← auto-created scrap sibling
            Scrap                       (dealer-level scrap)
    """
    location_type = (payload.get("location_type") or "van_loading").strip()
    if location_type != "van_loading":
        raise ValidationError("Only Van Loading locations can be created from this API.")

    # Validate assigned employee
    assigned_employee_id = payload.get("assigned_employee_id")
    if not assigned_employee_id:
        raise ValidationError("'assigned_employee_id' is required for Van Loading locations.")
    employee = _get_employee(env, assigned_employee_id)

    # Validate assigned distributor
    assigned_distributor_id = payload.get("assigned_distributor_id")
    if not assigned_distributor_id:
        raise ValidationError("'assigned_distributor_id' is required for Van Loading locations.")
    try:
        assigned_distributor_id = int(assigned_distributor_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'assigned_distributor_id' must be a valid integer.") from exc

    distributor = env["res.partner"].sudo().browse(assigned_distributor_id).exists()
    if not distributor or distributor.customer_type != "distributor":
        raise ValidationError("Assigned distributor not found.")
    if employee.distributor_contact_id and employee.distributor_contact_id != distributor:
        raise ValidationError("Assigned employee does not belong to the selected distributor.")

    # Van name entered by the user
    van_name = (payload.get("name") or "").strip()
    if not van_name:
        raise ValidationError("'name' (van name) is required.")

    # Ensure the dealer's dedicated location tree exists (idempotent).
    # This handles distributors created before the new location structure was introduced.
    ensure_distributor_locations(env, distributor)

    # Parent = Partners/<Dealer>/Stock  (the dealer's dedicated stock location)
    customer_default = env.ref("stock.stock_location_customers", raise_if_not_found=False)
    parent_location = distributor.property_stock_customer
    if not parent_location or parent_location == customer_default:
        raise ValidationError(
            "Distributor '%s' does not have a dedicated stock location. "
            "Please check the distributor setup." % distributor.name
        )

    stock_loc_name = "%s - Stock" % van_name
    return {
        "name": stock_loc_name,
        "location_id": parent_location.id,
        "usage": "customer",
        "ss_location_type": "van_loading",
        "ss_employee_id": employee.id,
        "ss_distributor_id": distributor.id,
    }


def create_van_scrap_sibling(env, stock_location, distributor_name, van_name):
    """Create the paired scrap location for a van under the same parent.

    Result: Partners/<Dealer>/Stock/<van_name> - Scrap
    """
    StockLocation = env["stock.location"].sudo()
    scrap_name = "%s - Scrap" % van_name

    # Avoid duplicates
    existing = StockLocation.search([
        ("name", "=", scrap_name),
        ("location_id", "=", stock_location.location_id.id),
        ("active", "=", True),
    ], limit=1)
    if existing:
        return existing

    scrap_loc = StockLocation.create({
        "name": scrap_name,
        "location_id": stock_location.location_id.id,
        "usage": "customer",
        "scrap_location": True,
        "ss_location_type": "van_loading",
        "ss_employee_id": stock_location.ss_employee_id.id if stock_location.ss_employee_id else False,
        "ss_distributor_id": stock_location.ss_distributor_id.id if stock_location.ss_distributor_id else False,
    })
    scrap_loc._compute_complete_name()
    scrap_loc.flush_recordset(["complete_name"])
    return scrap_loc


def _get_scrap_sibling(stock_location):
    """Find the scrap sibling of a van stock location (same parent, scrap=True)."""
    return stock_location.env["stock.location"].search([
        ("location_id", "=", stock_location.location_id.id),
        ("ss_location_type", "=", "van_loading"),
        ("scrap_location", "=", True),
        ("active", "=", True),
    ], limit=1)


def get_virtual_location_pagination(payload):
    return get_pagination(payload)



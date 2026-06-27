# -*- coding: utf-8 -*-
"""Return transfers: distributor customer location -> warehouse stock.

Thin flavor shim over ``transfer_common``. The shared engine holds all logic;
this module only defines the return-specific locations and re-exports the public
names the returns controller imports.
"""

from odoo.exceptions import ValidationError

# Re-exported so the returns controller can keep importing it from here.
from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination  # noqa: F401
from odoo.addons.meta_ss_transfer.utils import transfer_common as _tc


def _resolve_locations(env, distributor):
    """Source = distributor customer stock; destination = the warehouse stock."""
    source_location = distributor.property_stock_customer
    if not source_location:
        raise ValidationError("The assigned distributor has no customer stock location.")

    # Get the default warehouse (since there is only 1)
    warehouse = env["stock.warehouse"].sudo().search([("company_id", "in", [False, env.company.id])], limit=1)
    if not warehouse:
        raise ValidationError("No warehouse found for the company.")

    dest_location = warehouse.lot_stock_id
    if not dest_location:
        raise ValidationError("The warehouse has no stock location.")

    return source_location, dest_location, warehouse


RETURN = _tc.TransferFlavor(
    label="Return",
    resolve_locations=_resolve_locations,
    list_dest_leaf=("location_id.usage", "=", "customer"),
)


def get_employee_return_context(env, payload):
    return _tc.get_employee_context(env, payload, RETURN)


def serialize_return_prepare(env, payload):
    return _tc.serialize_prepare(env, payload, RETURN)


def build_return_product_domain(env, payload):
    return _tc.build_product_domain(env, payload, RETURN)


def serialize_return_products(env, products, source_location):
    return _tc.serialize_products(env, products, source_location)


def serialize_return_product_lots(env, payload, product_id):
    return _tc.serialize_product_lots(env, payload, product_id, RETURN)


def build_return_domain(env, payload):
    return _tc.build_list_domain(env, payload, RETURN)


def serialize_returns(pickings):
    return _tc.serialize_list(pickings)


def create_return_delivery(env, payload):
    return _tc.create_delivery(env, payload, RETURN)


def get_return_delivery_for_employee(env, picking_id, payload):
    return _tc.get_delivery_for_employee(env, picking_id, payload, RETURN)


def update_return_delivery(env, picking_id, payload):
    return _tc.update_delivery(env, picking_id, payload, RETURN)


def serialize_return_delivery(picking):
    return _tc.serialize_delivery(picking)

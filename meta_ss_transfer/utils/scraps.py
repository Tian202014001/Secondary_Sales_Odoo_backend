# -*- coding: utf-8 -*-
"""Scrap transfers: distributor scrap location -> company scrap location.

Thin flavor shim over ``transfer_common``. The shared engine holds all logic;
this module only defines the scrap-specific locations and re-exports the public
names the scraps controller imports.
"""

from odoo.exceptions import ValidationError

from odoo.addons.meta_ss_transfer.utils import transfer_common as _tc


def _resolve_locations(env, distributor):
    """Source = distributor scrap location; destination = the company scrap location."""
    source_location = distributor.scrap_location_id
    if not source_location:
        raise ValidationError("The assigned distributor has no scrap location.")

    # Get the scrap destination location
    dest_location = env["stock.location"].sudo().search(
        [("scrap_location", "=", True), ("company_id", "in", [False, env.company.id])], limit=1
    )
    if not dest_location:
        raise ValidationError("No scrap location found for the company.")

    warehouse = env["stock.warehouse"].sudo().search([("company_id", "in", [False, env.company.id])], limit=1)

    return source_location, dest_location, warehouse


SCRAP = _tc.TransferFlavor(
    label="Scrap",
    resolve_locations=_resolve_locations,
    list_dest_leaf=("location_dest_id.scrap_location", "=", True),
)


def get_employee_scrap_context(env, payload):
    return _tc.get_employee_context(env, payload, SCRAP)


def serialize_scrap_prepare(env, payload):
    return _tc.serialize_prepare(env, payload, SCRAP)


def build_scrap_product_domain(env, payload):
    return _tc.build_product_domain(env, payload, SCRAP)


def serialize_scrap_products(env, products, source_location):
    return _tc.serialize_products(env, products, source_location)


def serialize_scrap_product_lots(env, payload, product_id):
    return _tc.serialize_product_lots(env, payload, product_id, SCRAP)


def build_scrap_domain(env, payload):
    return _tc.build_list_domain(env, payload, SCRAP)


def serialize_scraps(pickings):
    return _tc.serialize_list(pickings)


def create_scrap_delivery(env, payload):
    return _tc.create_delivery(env, payload, SCRAP)


def get_scrap_delivery_for_employee(env, picking_id, payload):
    return _tc.get_delivery_for_employee(env, picking_id, payload, SCRAP)


def update_scrap_delivery(env, picking_id, payload):
    return _tc.update_delivery(env, picking_id, payload, SCRAP)


def serialize_scrap_delivery(picking):
    return _tc.serialize_delivery(picking)


def validate_scrap_delivery(env, picking_id, payload):
    return _tc.validate_delivery(env, picking_id, payload, SCRAP)


def cancel_scrap_delivery(env, picking_id, payload):
    return _tc.cancel_delivery(env, picking_id, payload, SCRAP)


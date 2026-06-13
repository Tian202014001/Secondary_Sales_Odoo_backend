# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

def _get_float(value, field_name):
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'%s' must be numeric." % field_name) from exc

def _get_positive_float(value, field_name):
    value = _get_float(value, field_name)
    if value <= 0:
        raise ValidationError("'%s' must be greater than zero." % field_name)
    return value

def _get_integer_id(value, field_name):
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'%s' must be a valid integer id." % field_name) from exc

def _get_employee(env, employee_id):
    if not employee_id:
        raise ValidationError("'employee_id' is required.")
    try:
        employee_id = int(employee_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'employee_id' must be a valid integer id.") from exc
    employee = env["hr.employee"].sudo().browse(employee_id).exists()
    if not employee:
        raise ValidationError("Employee not found.")
    return employee

def _create_move_line(env, picking, move, quantity, lot=None):
    env["stock.move.line"].sudo().create({
        "picking_id": picking.id,
        "move_id": move.id,
        "company_id": picking.company_id.id,
        "product_id": move.product_id.id,
        "product_uom_id": move.product_uom.id,
        "quantity": quantity,
        "picked": True,
        "lot_id": lot.id if lot else False,
        "location_id": move.location_id.id,
        "location_dest_id": move.location_dest_id.id,
    })

def _get_lot(env, product, lot_id):
    if not lot_id:
        raise ValidationError("'lot_id' is required.")
    try:
        lot_id = int(lot_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'lot_id' must be a valid integer id.") from exc
    lot = env["stock.lot"].sudo().browse(lot_id).exists()
    if not lot:
        raise ValidationError("Lot not found.")
    if lot.product_id != product:
        raise ValidationError("Lot '%s' does not belong to product '%s'." % (lot.name, product.display_name))
    return lot

def _auto_assign_lots(env, product, quantity, source_location, picking=None):
    """Assign lots FIFO from source_location.

    When a picking is supplied its own reservations are added back to
    available_quantity so that changing the source location on an already-
    reserved delivery still produces correct lot suggestions.
    """
    if product.tracking == "none":
        return []

    # Build a map of lot_id → qty reserved by this picking (at any location).
    # These units are being re-allocated, so they count as available.
    picking_reserved = {}
    if picking:
        for ml in picking.sudo().move_line_ids.filtered(
            lambda l: l.product_id == product and l.lot_id
        ):
            picking_reserved[ml.lot_id.id] = (
                picking_reserved.get(ml.lot_id.id, 0.0) + ml.quantity
            )

    quants = env["stock.quant"].sudo().search([
        ("product_id", "=", product.id),
        ("location_id", "child_of", source_location.id),
        ("lot_id", "!=", False),
    ], order="in_date asc, id asc")

    lot_lines = []
    remaining = quantity
    for quant in quants:
        if float_compare(remaining, 0.0, precision_rounding=product.uom_id.rounding) <= 0:
            break
        effective_qty = quant.available_quantity + picking_reserved.get(quant.lot_id.id, 0.0)
        if float_compare(effective_qty, 0.0, precision_rounding=product.uom_id.rounding) <= 0:
            continue
        take = min(effective_qty, remaining)
        if product.tracking == "serial":
            take = 1.0
        lot_lines.append({
            "lot_id": quant.lot_id.id,
            "lot_name": quant.lot_id.name,
            "quantity": take,
        })
        remaining -= take

    if float_compare(remaining, 0.0, precision_rounding=product.uom_id.rounding) > 0:
        raise ValidationError(
            "Not enough tracked stock available for product '%s'. Missing %.2f %s."
            % (product.display_name, remaining, product.uom_id.name)
        )

    return lot_lines

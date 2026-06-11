# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError

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

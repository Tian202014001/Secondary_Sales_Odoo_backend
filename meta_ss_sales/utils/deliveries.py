# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.addons.meta_ss_rest_api.utils.helpers import _create_move_line, _get_float, _get_lot
from odoo.tools.float_utils import float_compare, float_is_zero

from odoo.addons.meta_ss_sales.utils.sale_order_details import (
    get_primary_sale_order_for_employee,
    serialize_sale_order_detail,
)
from odoo.addons.meta_ss_sales.utils.sales import parse_bool
from odoo.addons.meta_ss_rest_api.utils.warehouses import get_warehouse


def resolve_delivery_location(env, payload):
    """Resolve source location from payload without requiring sale_order_id.

    Returns the location if resolvable from payload alone, or None so the caller
    can fall back to picking.location_id.
    """
    location_id = payload.get("location_id") or payload.get("source_location_id")
    if location_id:
        try:
            location_id = int(location_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'location_id' must be a valid integer id.") from exc
        location = env["stock.location"].sudo().browse(location_id).exists()
        if not location:
            raise ValidationError("Source location not found.")
        return location

    warehouse_id = payload.get("warehouse_id")
    if warehouse_id:
        warehouse = get_warehouse(env, warehouse_id)
        if not warehouse.lot_stock_id:
            raise ValidationError("The selected warehouse has no stock location.")
        return warehouse.lot_stock_id

    return None


def get_order_delivery_context(env, order_id, payload):
    order = get_primary_sale_order_for_employee(env, order_id, payload)
    picking = _get_active_delivery_picking(order, payload.get("picking_id"))
    return order, picking


def get_delivery_context_by_payload(env, payload):
    """Return delivery context from a payload containing order_id/sale_order_id."""
    order_id = payload.get("sale_order_id") or payload.get("order_id")
    if not order_id:
        raise ValidationError("'sale_order_id' is required.")
    return get_order_delivery_context(env, order_id, payload)


def get_delivery_context_by_picking(env, picking_id, payload):
    """Return delivery context from a picking id and employee payload."""
    if not picking_id:
        raise ValidationError("'picking_id' is required.")
    try:
        picking_id = int(picking_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'picking_id' must be a valid integer id.") from exc

    picking = env["stock.picking"].sudo().browse(picking_id).exists()
    if not picking:
        raise ValidationError("No delivery was found for the provided picking id.")
    if not picking.sale_id:
        raise ValidationError("The requested delivery is not linked to a sale order.")

    payload = {**payload, "picking_id": picking.id}
    return get_order_delivery_context(env, picking.sale_id.id, payload)


def serialize_delivery_prepare(env, order, picking):
    warehouses = env["stock.warehouse"].sudo().search([
        ("company_id", "in", [False, order.company_id.id]),
    ], order="name")
    locations = env["stock.location"].sudo().search([
        ("usage", "=", "internal"),
        ("company_id", "in", [False, order.company_id.id]),
    ], order="complete_name, id")
    return {
        "order": {
            "id": order.id,
            "name": order.name,
            "state": order.state,
            "distributor": {
                "id": order.partner_id.id,
                "name": order.partner_id.name,
            } if order.partner_id else None,
        },
        "picking": serialize_picking_detail(picking),
        "warehouses": [
            {
                "id": warehouse.id,
                "name": warehouse.name,
                "code": warehouse.code,
                "stock_location": {
                    "id": warehouse.lot_stock_id.id,
                    "name": warehouse.lot_stock_id.display_name,
                } if warehouse.lot_stock_id else None,
            }
            for warehouse in warehouses
        ],
        "locations": [
            {
                "id": loc.id,
                "name": loc.display_name,
                "complete_name": loc.complete_name,
                "usage": loc.usage,
            }
            for loc in locations
        ],
    }


def serialize_picking_detail(picking):
    picking = picking.sudo()
    return {
        "id": picking.id,
        "name": picking.name,
        "state": picking.state,
        "scheduled_date": str(picking.scheduled_date) if picking.scheduled_date else None,
        "source_location": {
            "id": picking.location_id.id,
            "name": picking.location_id.display_name,
        } if picking.location_id else None,
        "destination_location": {
            "id": picking.location_dest_id.id,
            "name": picking.location_dest_id.display_name,
        } if picking.location_dest_id else None,
        "lines": [_serialize_move(move) for move in _get_deliverable_moves(picking)],
    }


def validate_delivery(env, order, picking, payload):
    if picking.state in ("done", "cancel"):
        raise ValidationError("This delivery cannot be validated in its current state.")

    _apply_warehouse_to_picking(env, picking, payload)
    _apply_delivery_lines(env, picking, payload.get("lines") or [])

    create_backorder = parse_bool(payload["create_backorder"]) if "create_backorder" in payload else True
    context = {
        "skip_backorder": True,
        "button_validate_picking_ids": picking.ids,
    }
    if not create_backorder:
        context["picking_ids_not_to_backorder"] = picking.ids

    result = picking.with_context(**context).button_validate()
    return {
        "validation_result": True if result is True else result,
        "order": serialize_sale_order_detail(order),
    }


def perform_delivery_action(env, picking_id, payload):
    """Run a supported stock delivery action."""
    action = (payload.get("action") or "").strip().lower()
    if not action:
        raise ValidationError("'action' is required.")

    order, picking = get_delivery_context_by_picking(env, picking_id, payload)
    if action == "validate":
        return validate_delivery(env, order, picking, payload)

    if action == "cancel":
        if picking.state == "done":
            raise ValidationError("Done deliveries cannot be cancelled.")
        if picking.state != "cancel":
            picking.action_cancel()
        return {
            "validation_result": True,
            "order": serialize_sale_order_detail(order),
        }

    raise ValidationError("Unsupported delivery action '%s'." % action)


def _get_active_delivery_picking(order, picking_id=None):
    if picking_id:
        try:
            picking_id = int(picking_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'picking_id' must be a valid integer id.") from exc
        picking = order.picking_ids.filtered(lambda item: item.id == picking_id)
        if not picking:
            raise ValidationError("No delivery was found for this order and picking id.")
        return picking[:1]

    pickings = order.picking_ids.filtered(lambda picking: picking.state not in ("done", "cancel"))
    if not pickings:
        raise ValidationError("No active delivery was found for this order.")
    return pickings.sorted(lambda item: item.id)[:1]


def _get_deliverable_moves(picking):
    if picking.state in ("done", "cancel"):
        return picking.move_ids.sorted(lambda move: (move.sequence, move.id))
    return picking.move_ids.filtered(
        lambda move: move.state not in ("done", "cancel") and move.product_uom_qty > 0
    ).sorted(lambda move: (move.sequence, move.id))


def _serialize_move(move):
    ordered_qty = move.product_uom_qty
    current_done_qty = move.quantity
    return {
        "move_id": move.id,
        "sale_line_id": move.sale_line_id.id if move.sale_line_id else None,
        "product": {
            "id": move.product_id.id,
            "name": move.product_id.display_name,
            "default_code": move.product_id.default_code or None,
            "tracking": move.product_id.tracking,
        } if move.product_id else None,
        "product_uom_qty": ordered_qty,
        "quantity_done": current_done_qty,
        "remaining_qty": ordered_qty,
        "default_delivery_qty": current_done_qty,
        "product_uom": {
            "id": move.product_uom.id,
            "name": move.product_uom.name,
        } if move.product_uom else None,
        "lot_lines": [_serialize_move_line(line) for line in move.move_line_ids if line.quantity],
    }


def _serialize_move_line(line):
    return {
        "move_line_id": line.id,
        "lot": {
            "id": line.lot_id.id,
            "name": line.lot_id.name,
        } if line.lot_id else None,
        "quantity": line.quantity,
        "location": {
            "id": line.location_id.id,
            "name": line.location_id.display_name,
        } if line.location_id else None,
    }


def _apply_warehouse_to_picking(env, picking, payload):
    location_id = payload.get("location_id") or payload.get("source_location_id")
    if location_id:
        try:
            location_id = int(location_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'location_id' must be a valid integer id.") from exc
        location = env["stock.location"].sudo().browse(location_id).exists()
        if not location:
            raise ValidationError("No stock location was found for the provided 'location_id'.")
    else:
        warehouse_id = payload.get("warehouse_id")
        if not warehouse_id:
            return

        warehouse = get_warehouse(env, warehouse_id)
        if not warehouse.lot_stock_id:
            raise ValidationError("The selected warehouse has no stock location.")
        location = warehouse.lot_stock_id

    picking.write({"location_id": location.id})
    picking.move_ids.filtered(lambda move: move.state not in ("done", "cancel")).write({
        "location_id": location.id,
    })
    picking.move_line_ids.filtered(lambda line: line.state not in ("done", "cancel")).write({
        "location_id": location.id,
    })


def _apply_delivery_lines(env, picking, lines):
    if not isinstance(lines, list) or not lines:
        raise ValidationError("'lines' must be a non-empty list.")

    moves_by_id = {move.id: move for move in _get_deliverable_moves(picking)}
    touched_moves = picking.move_ids.browse()
    for line in lines:
        if not isinstance(line, dict):
            raise ValidationError("Each delivery line must be an object.")
        move = _get_payload_move(moves_by_id, line.get("move_id"))
        touched_moves |= move
        quantity = _get_float(line.get("quantity_done", line.get("quantity", 0.0)), "quantity_done")
        _validate_move_quantity(move, quantity)
        _rewrite_move_lines(env, picking, move, quantity, line.get("lot_lines") or [])

    untouched = _get_deliverable_moves(picking) - touched_moves
    if untouched:
        untouched.write({"quantity": 0, "picked": False})
        untouched.mapped("move_line_ids").unlink()


def _get_payload_move(moves_by_id, move_id):
    if not move_id:
        raise ValidationError("'move_id' is required for each delivery line.")
    try:
        move_id = int(move_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'move_id' must be a valid integer id.") from exc
    move = moves_by_id.get(move_id)
    if not move:
        raise ValidationError("A delivery line references a move that is not deliverable.")
    return move


def _validate_move_quantity(move, quantity):
    if quantity < 0:
        raise ValidationError("'quantity_done' cannot be negative.")
    if float_compare(quantity, move.product_uom_qty, precision_rounding=move.product_uom.rounding) > 0:
        raise ValidationError(
            "Delivered quantity cannot exceed ordered quantity for product '%s'."
            % move.product_id.display_name
        )


def _rewrite_move_lines(env, picking, move, quantity, lot_lines):
    move.move_line_ids.unlink()

    if float_is_zero(quantity, precision_rounding=move.product_uom.rounding):
        move.write({"quantity": 0, "picked": False})
        return

    tracking = move.product_id.tracking
    if tracking == "none":
        _create_move_line(env, picking, move, quantity)
    else:
        _create_tracked_move_lines(env, picking, move, quantity, lot_lines)

    move.write({"picked": True})
    move.move_line_ids.write({"picked": True})


def _create_tracked_move_lines(env, picking, move, quantity, lot_lines):
    if not isinstance(lot_lines, list) or not lot_lines:
        raise ValidationError("Lot allocation is required for product '%s'." % move.product_id.display_name)

    total_allocated = 0.0
    for lot_line in lot_lines:
        if not isinstance(lot_line, dict):
            raise ValidationError("Each lot line must be an object.")
        lot = _get_lot(env, move.product_id, lot_line.get("lot_id"))
        lot_qty = _get_float(lot_line.get("quantity", 0.0), "lot quantity")
        if lot_qty <= 0:
            raise ValidationError("Lot quantity must be greater than zero.")
        if move.product_id.tracking == "serial" and float_compare(
            lot_qty, 1.0, precision_rounding=move.product_uom.rounding
        ) > 0:
            raise ValidationError("Serial-tracked products must be delivered one unit per lot/serial.")
        total_allocated += lot_qty
        _create_move_line(env, picking, move, lot_qty, lot=lot)

    if float_compare(total_allocated, quantity, precision_rounding=move.product_uom.rounding) != 0:
        raise ValidationError("Total lot allocated quantity must match delivery quantity.")



def get_delivery_pagination(payload):
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


def build_delivery_domain(payload):
    domain = [("picking_type_id.code", "=", "outgoing")]
    
    employee_id = payload.get("employee_id")
    if employee_id:
        domain.append(("sale_id.so_employee_id", "child_of", int(employee_id)))

    state = payload.get("state")
    if state and state != "all":
        domain.append(("state", "=", str(state)))

    picking_type = payload.get("picking_type") or payload.get("type") or payload.get("sale_type")
    if picking_type:
        domain.append(("ss_picking_type", "=", picking_type))

    search = (payload.get("search") or "").strip()
    if search:
        search_domain = [
            "|", "|", "|",
            ("name", "ilike", search),
            ("origin", "ilike", search),
            ("sale_id.name", "ilike", search),
            ("partner_id.name", "ilike", search),
        ]
        from odoo.osv import expression
        domain = expression.AND([domain, search_domain])

    return domain


def serialize_delivery_list_item(picking):
    return {
        "id": picking.id,
        "name": picking.name,
        "state": picking.state,
        "partner": {
            "id": picking.partner_id.id,
            "name": picking.partner_id.name,
        } if picking.partner_id else None,
        "created_date": picking.create_date.isoformat() + "Z" if picking.create_date else None,
        "scheduled_date": picking.scheduled_date.isoformat() + "Z" if picking.scheduled_date else None,
        "date_done": picking.date_done.isoformat() + "Z" if picking.date_done else None,
        "origin": picking.origin,
        "sale_id": picking.sale_id.id if picking.sale_id else None,
        "sale_name": picking.sale_id.name if picking.sale_id else None,
    }

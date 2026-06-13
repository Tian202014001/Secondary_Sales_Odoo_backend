# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError


def get_request_employee(env, payload):
    """Return the employee requested by the mobile app.

    Authentication will replace this later. For now, every detail/action API
    requires employee_id so one sales employee cannot browse another employee's
    orders through the mobile app.
    """
    employee_id = payload.get("employee_id")
    if not employee_id:
        raise ValidationError("'employee_id' is required.")
    try:
        employee_id = int(employee_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'employee_id' must be a valid integer id.") from exc

    employee = env["hr.employee"].sudo().browse(employee_id).exists()
    if not employee:
        raise ValidationError("No employee was found for the provided 'employee_id'.")
    return employee


def get_primary_sale_order_for_employee(env, order_id, payload):
    """Return a primary sale order visible to the requested employee."""
    return get_sale_order_for_employee(env, order_id, {**payload, "sale_type": "primary"})


def get_sale_order_for_employee(env, order_id, payload):
    """Return a sale order visible to the requested employee."""
    employee = get_request_employee(env, payload)
    try:
        order_id = int(order_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'order_id' must be a valid integer id.") from exc

    order = env["sale.order"].sudo().browse(order_id).exists()
    if not order:
        raise ValidationError("No sale order was found for the provided id.")
    sale_type = payload.get("sale_type")
    if sale_type and sale_type != "all" and order.sale_type != sale_type:
        raise ValidationError("The requested order does not match 'sale_type'.")
    if order.so_employee_id and order.so_employee_id != employee:
        raise ValidationError("This sale order does not belong to the requested employee.")
    return order


def perform_sale_order_action(env, order_id, payload):
    """Run a supported action against a sale order."""
    action = (payload.get("action") or "").strip().lower()
    if not action:
        raise ValidationError("'action' is required.")

    order = get_sale_order_for_employee(env, order_id, payload)
    if action == "cancel":
        if order.state == "cancel":
            raise ValidationError("This sale order is already cancelled.")
        if order.state in ("done",):
            raise ValidationError("This sale order cannot be cancelled in its current state.")
        order.action_cancel()
        return order

    if action == "confirm":
        if order.state not in ("draft", "sent"):
            raise ValidationError("This sale order cannot be confirmed in its current state.")
        order.action_confirm()
        return order

    raise ValidationError("Unsupported sale order action '%s'." % action)


def serialize_sale_order_detail(order):
    """Serialize the order detail screen payload."""
    order = order.sudo()
    return {
        "id": order.id,
        "name": order.name,
        "sale_type": order.sale_type,
        "state": order.state,
        "state_label": dict(order._fields["state"].selection).get(order.state, order.state),
        "date_order": str(order.date_order) if order.date_order else None,
        "expected_delivery_date": str(order.commitment_date) if order.commitment_date else None,
        "client_order_ref": order.client_order_ref or None,
        "can_cancel": order.state not in ("cancel", "done"),
        "can_validate_delivery": any(
            picking.state not in ("done", "cancel") for picking in order.picking_ids
        ),
        "distributor": {
            "id": order.partner_id.id,
            "name": order.partner_id.name,
            "phone": order.partner_id.phone or order.partner_id.mobile or None,
            "address": _partner_address(order.partner_id),
        } if order.partner_id else None,
        "employee": {
            "id": order.so_employee_id.id,
            "name": order.so_employee_id.name,
        } if order.so_employee_id else None,
        "amounts": _serialize_order_amounts(order),
        "lines": [_serialize_sale_line(line) for line in order.order_line],
        "delivery_orders": [_serialize_picking_summary(picking) for picking in order.picking_ids],
    }


def _partner_address(partner):
    parts = [
        partner.street,
        partner.street2,
        partner.city,
        partner.state_id.name if partner.state_id else None,
        partner.zip,
        partner.country_id.name if partner.country_id else None,
    ]
    return ", ".join(part for part in parts if part) or None


def _serialize_order_amounts(order):
    posted_invoices = order.invoice_ids.filtered(lambda invoice: invoice.state == "posted")
    receivable = sum(posted_invoices.mapped("amount_residual"))
    discount = sum(
        line.price_unit * line.product_uom_qty * line.discount / 100.0
        for line in order.order_line
    )
    return {
        "amount_untaxed": order.amount_untaxed,
        "amount_tax": order.amount_tax,
        "amount_total": order.amount_total,
        "discount": discount,
        "receivable": receivable,
        "currency": {
            "id": order.currency_id.id,
            "name": order.currency_id.name,
            "symbol": order.currency_id.symbol,
        } if order.currency_id else None,
    }


def _serialize_sale_line(line):
    delivered_qty = line.qty_delivered
    ordered_qty = line.product_uom_qty
    return {
        "id": line.id,
        "product": {
            "id": line.product_id.id,
            "name": line.product_id.display_name,
            "default_code": line.product_id.default_code or None,
            "tracking": line.product_id.tracking,
        } if line.product_id else None,
        "product_uom_qty": ordered_qty,
        "qty_delivered": delivered_qty,
        "balance_qty": max(ordered_qty - delivered_qty, 0.0),
        "product_uom": {
            "id": line.product_uom.id,
            "name": line.product_uom.name,
        } if line.product_uom else None,
        "price_unit": line.price_unit,
        "discount": line.discount,
        "price_subtotal": line.price_subtotal,
        "price_total": line.price_total,
    }


def _serialize_picking_summary(picking):
    return {
        "id": picking.id,
        "name": picking.name,
        "state": picking.state,
        "state_label": dict(picking._fields["state"].selection).get(picking.state, picking.state),
        "scheduled_date": str(picking.scheduled_date) if picking.scheduled_date else None,
        "source_location": {
            "id": picking.location_id.id,
            "name": picking.location_id.display_name,
        } if picking.location_id else None,
        "destination_location": {
            "id": picking.location_dest_id.id,
            "name": picking.location_dest_id.display_name,
        } if picking.location_dest_id else None,
    }

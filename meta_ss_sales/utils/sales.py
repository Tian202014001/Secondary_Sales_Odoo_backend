from odoo.addons.meta_ss_rest_api.utils.helpers import _get_float, _get_positive_float
# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.osv import expression

from odoo.addons.meta_ss_rest_api.utils.mobile_policy import MobilePolicy


def get_sales_pagination(payload):
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


def build_sale_order_domain(payload):
    """Build a sale.order search domain using sale_type and common filters."""
    sale_type = (payload.get("sale_type") or "primary").strip()
    domain = []
    
    employee_id = payload.get("employee_id")
    if employee_id:
        domain = expression.AND([
            domain,
            expression.OR([
                [("so_employee_id", "child_of", int(employee_id))],
                [("user_id.employee_id", "child_of", int(employee_id))]
            ])
        ])

    if sale_type and sale_type != "all":
        domain.append(("sale_type", "=", sale_type))

    state = payload.get("state") or payload.get("status")
    if state and state != "all":
      domain.append(("state", "=", str(state)))

    distributor_id = payload.get("distributor_id")
    if distributor_id:
        try:
            distributor_id = int(distributor_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'distributor_id' must be a valid integer id.") from exc
        domain.append(("partner_id", "=", distributor_id))

    search = (payload.get("search") or payload.get("customer") or "").strip()
    if search:
        search_domain = expression.OR([
            [("partner_id.name", "ilike", search)],
            [("partner_id.phone", "ilike", search)],
            [("partner_id.mobile", "ilike", search)],
            [("name", "ilike", search)],
        ])
        domain = expression.AND([domain, search_domain])

    date_from = payload.get("date_from") or payload.get("start_date")
    if date_from:
        domain.append(("date_order", ">=", "%s 00:00:00" % date_from))

    date_to = payload.get("date_to") or payload.get("end_date")
    if date_to:
        domain.append(("date_order", "<=", "%s 23:59:59" % date_to))

    if not date_from and not date_to:
        order_date = payload.get("date") or payload.get("order_date")
        if order_date:
            order_date = str(order_date)
            domain.append(("date_order", ">=", "%s 00:00:00" % order_date))
            domain.append(("date_order", "<=", "%s 23:59:59" % order_date))



    return domain


def get_distributor(env, distributor_id, employee=None):
    """Return a distributor contact or raise a validation error."""
    if not distributor_id:
        raise ValidationError("'distributor_id' is required.")
    try:
        distributor_id = int(distributor_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'distributor_id' must be a valid integer id.") from exc

    distributor = env["res.partner"].sudo().browse(distributor_id).exists()
    if not distributor:
        raise ValidationError("No distributor was found for the provided 'distributor_id'.")
    if distributor.customer_type != "distributor":
        raise ValidationError("'distributor_id' must be a distributor contact.")
    if employee:
        visible_distributor_ids = MobilePolicy.visible_distributor_ids(env, employee)
        if not visible_distributor_ids:
            raise ValidationError(
                "No distributors are assigned to the requesting employee or their team."
            )
        if distributor.id not in visible_distributor_ids:
            raise ValidationError(
                "The selected distributor is not visible to the requesting employee."
            )

    return distributor


def get_employee(env, employee_id):
    """Return an employee if provided, otherwise return an empty recordset."""
    if not employee_id:
        return env["hr.employee"]
    try:
        employee_id = int(employee_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'employee_id' must be a valid integer id.") from exc

    employee = env["hr.employee"].sudo().browse(employee_id).exists()
    if not employee:
        raise ValidationError("No employee was found for the provided 'employee_id'.")

    return employee


def prepare_sale_order_values(env, payload):
    """Build validated sale.order values for sale.order creation."""
    sale_type = (payload.get("sale_type") or "primary").strip()

    employee = get_employee(env, payload.get("employee_id"))
    distributor = get_distributor(env, payload.get("distributor_id"), employee=employee)
    order_lines = payload.get("order_lines") or payload.get("lines") or []
    if not isinstance(order_lines, list) or not order_lines:
        raise ValidationError("'order_lines' must be a non-empty list.")

    values = {
        "partner_id": distributor.id,
        "partner_shipping_id": distributor.id,
        "sale_type": sale_type,
        "order_line": _prepare_sale_order_line_commands(env, order_lines),
    }
    if employee:
        values["so_employee_id"] = employee.id
    warehouse_id = payload.get("warehouse_id")
    if warehouse_id:
        try:
            warehouse_id = int(warehouse_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'warehouse_id' must be a valid integer id.") from exc
        values["warehouse_id"] = warehouse_id

    if employee:
        values["so_employee_id"] = employee.id
        if employee.user_id:
            values["user_id"] = employee.user_id.id

    if payload.get("client_order_ref"):
        values["client_order_ref"] = payload.get("client_order_ref")
    if payload.get("note"):
        values["note"] = payload.get("note")
    if payload.get("expected_delivery_date"):
        values["commitment_date"] = payload.get("expected_delivery_date")

    return values


def _prepare_sale_order_line_commands(env, order_lines):
    """Build sale.order order_line commands from API payload."""
    commands = []
    for index, line in enumerate(order_lines, start=1):
        if not isinstance(line, dict):
            raise ValidationError("Each order line must be an object.")

        product = _get_saleable_product(env, line.get("product_id"))
        quantity = _get_positive_float(
            line.get("product_uom_qty", line.get("quantity", line.get("qty", 0))),
            "product_uom_qty",
        )

        values = {
            "product_id": product.id,
            "product_uom_qty": quantity,
            "sequence": _get_int(line.get("sequence", index * 10), "sequence"),
        }
        if line.get("uom_id"):
            uom = _get_product_uom(env, line.get("uom_id"), product)
            values["product_uom"] = uom.id
        if "price_unit" in line:
            values["price_unit"] = _get_float(line.get("price_unit"), "price_unit")
        if "discount" in line:
            values["discount"] = _get_float(line.get("discount"), "discount")
        if line.get("description"):
            values["name"] = line.get("description")

        commands.append((0, 0, values))

    return commands


def update_sale_order_lines(env, order, order_lines, was_confirmed):
    """Reconcile and update order lines in-place, conforming to Odoo's native workflow."""
    existing_lines = {line.product_id.id: line for line in order.order_line if not line.display_type}
    payload_product_ids = set()

    line_commands = []
    for index, line in enumerate(order_lines, start=1):
        if not isinstance(line, dict):
            raise ValidationError("Each order line must be an object.")

        prod_id = int(line.get("product_id"))
        payload_product_ids.add(prod_id)
        product = _get_saleable_product(env, prod_id)
        quantity = _get_positive_float(
            line.get("product_uom_qty", line.get("quantity", line.get("qty", 0))),
            "product_uom_qty",
        )

        values = {
            "product_uom_qty": quantity,
            "sequence": _get_int(line.get("sequence", index * 10), "sequence"),
        }
        if line.get("uom_id"):
            uom = _get_product_uom(env, line.get("uom_id"), product)
            values["product_uom"] = uom.id
        if "price_unit" in line:
            values["price_unit"] = _get_float(line.get("price_unit"), "price_unit")
        if "discount" in line:
            values["discount"] = _get_float(line.get("discount"), "discount")
        if line.get("description"):
            values["name"] = line.get("description")

        if prod_id in existing_lines:
            existing_line = existing_lines[prod_id]
            line_commands.append((1, existing_line.id, values))
        else:
            values["product_id"] = product.id
            line_commands.append((0, 0, values))

    for prod_id, existing_line in existing_lines.items():
        if prod_id not in payload_product_ids:
            if was_confirmed:
                line_commands.append((1, existing_line.id, {"product_uom_qty": 0.0}))
            else:
                line_commands.append((2, existing_line.id, 0))

    if line_commands:
        order.sudo().write({"order_line": line_commands})


def _get_saleable_product(env, product_id):
    """Return a saleable product or raise a validation error."""
    if not product_id:
        raise ValidationError("'product_id' is required for each order line.")
    try:
        product_id = int(product_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'product_id' must be a valid integer id.") from exc

    product = env["product.product"].sudo().browse(product_id).exists()
    if not product:
        raise ValidationError("No product was found for one of the order lines.")
    if not product.sale_ok:
        raise ValidationError("Product '%s' is not allowed on sales orders." % product.display_name)

    return product


def _get_product_uom(env, uom_id, product):
    """Return a UoM compatible with the product category."""
    try:
        uom_id = int(uom_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'uom_id' must be a valid integer id.") from exc

    uom = env["uom.uom"].sudo().browse(uom_id).exists()
    if not uom:
        raise ValidationError("No unit of measure was found for one of the order lines.")
    if uom.category_id != product.uom_id.category_id:
        raise ValidationError("The selected unit of measure does not match product '%s'." % product.display_name)

    return uom



def _get_int(value, field_name):
    """Return an integer value or raise a validation error."""
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'%s' must be an integer." % field_name) from exc


def parse_bool(value):
    """Return a boolean from common API payload formats."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "")
    return bool(value)


def serialize_sale_order(order):
    """Serialize one sale.order for API response."""
    delivery_status = "no"
    try:
        delivery_status = order.delivery_status or "no"
    except AttributeError:
        if order.picking_ids:
            states = [p.state for p in order.picking_ids]
            if all(s == "done" for s in states):
                delivery_status = "full"
            elif any(s == "done" for s in states) or any(s in ("assigned", "confirmed") for s in states):
                delivery_status = "partial"

    return {
        "id": order.id,
        "name": order.name,
        "sale_type": order.sale_type,
        "state": order.state,
        "delivery_status": delivery_status,
        "warehouse": {
            "id": order.warehouse_id.id,
            "name": order.warehouse_id.name,
        } if order.warehouse_id else None,
        "date_order": str(order.date_order) if order.date_order else None,
        "client_order_ref": order.client_order_ref or None,
        "distributor": {
            "id": order.partner_id.id,
            "name": order.partner_id.name,
            "customer_stock_location": {
                "id": order.partner_id.property_stock_customer.id,
                "name": order.partner_id.property_stock_customer.name,
                "display_name": order.partner_id.property_stock_customer.display_name,
                "usage": order.partner_id.property_stock_customer.usage,
            } if order.partner_id.property_stock_customer else None,
        } if order.partner_id else None,
        "employee": {
            "id": order.so_employee_id.id,
            "name": order.so_employee_id.name,
        } if order.so_employee_id else None,
        "amount_untaxed": order.amount_untaxed,
        "amount_tax": order.amount_tax,
        "amount_total": order.amount_total,
        "lines": [
            {
                "id": line.id,
                "product": {
                    "id": line.product_id.id,
                    "name": line.product_id.display_name,
                    "default_code": line.product_id.default_code or None,
                } if line.product_id else None,
                "product_uom_qty": line.product_uom_qty,
                "product_uom": {
                    "id": line.product_uom.id,
                    "name": line.product_uom.name,
                } if line.product_uom else None,
                "price_unit": line.price_unit,
                "discount": line.discount,
                "price_subtotal": line.price_subtotal,
                "price_total": line.price_total,
            }
            for line in order.order_line
        ],
        "delivery_orders": [
            {
                "id": picking.id,
                "name": picking.name,
                "state": picking.state,
                "source_location": {
                    "id": picking.location_id.id,
                    "name": picking.location_id.display_name,
                } if picking.location_id else None,
                "destination_location": {
                    "id": picking.location_dest_id.id,
                    "name": picking.location_dest_id.display_name,
                } if picking.location_dest_id else None,
            }
            for picking in order.picking_ids
        ],
    }

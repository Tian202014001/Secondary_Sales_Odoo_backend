# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.osv import expression

from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination


def build_warehouse_domain(env, payload):
    domain = [("company_id", "in", [False, env.company.id])]
    search = (payload.get("search") or "").strip()
    if search:
        domain = expression.AND([
            domain,
            expression.OR([
                [("name", "ilike", search)],
                [("code", "ilike", search)],
            ]),
        ])
    return domain


def serialize_warehouse(warehouse):
    return {
        "id": warehouse.id,
        "name": warehouse.name,
        "code": warehouse.code,
        "stock_location": {
            "id": warehouse.lot_stock_id.id,
            "name": warehouse.lot_stock_id.display_name,
            "usage": warehouse.lot_stock_id.usage,
        } if warehouse.lot_stock_id else None,
    }


def get_warehouse(env, warehouse_id=None, location_id=None):
    if warehouse_id:
        try:
            warehouse_id = int(warehouse_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'warehouse_id' must be a valid integer id.") from exc
        warehouse = env["stock.warehouse"].sudo().browse(warehouse_id).exists()
        if not warehouse:
            raise ValidationError("No warehouse was found for the provided 'warehouse_id'.")
        return warehouse

    if location_id:
        location = get_stock_location(env, location_id)
        warehouse = env["stock.warehouse"].sudo().search([
            ("view_location_id", "parent_of", location.id),
        ], limit=1)
        if warehouse:
            return warehouse

    return env["stock.warehouse"]


def get_stock_location(env, location_id):
    if not location_id:
        raise ValidationError("'location_id' is required.")
    try:
        location_id = int(location_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'location_id' must be a valid integer id.") from exc

    location = env["stock.location"].sudo().browse(location_id).exists()
    if not location:
        raise ValidationError("No stock location was found for the provided 'location_id'.")
    return location


def get_warehouse_location(env, payload):
    warehouse = get_warehouse(env, payload.get("warehouse_id"))
    if warehouse:
        if not warehouse.lot_stock_id:
            raise ValidationError("The selected warehouse has no stock location.")
        return warehouse.lot_stock_id
    if payload.get("location_id"):
        return get_stock_location(env, payload.get("location_id"))
    raise ValidationError("'warehouse_id' or 'location_id' is required.")


def get_warehouse_pagination(payload):
    return get_pagination(payload)


def build_available_lot_domain(env, payload):
    product = _get_product(env, payload.get("product_id"))
    location = get_warehouse_location(env, payload)
    domain = [
        ("product_id", "=", product.id),
        ("location_id", "child_of", location.id),
        ("available_quantity", ">", 0),
        ("lot_id", "!=", False),
    ]
    return product, location, domain


def serialize_available_lots(quants):
    data = []
    for quant in quants:
        data.append({
            "lot_id": quant.lot_id.id,
            "lot_name": quant.lot_id.name,
            "product_id": quant.product_id.id,
            "available_qty": quant.available_quantity,
            "quantity": quant.quantity,
            "reserved_quantity": quant.reserved_quantity,
            "uom": {
                "id": quant.product_uom_id.id,
                "name": quant.product_uom_id.name,
            } if quant.product_uom_id else None,
            "location": {
                "id": quant.location_id.id,
                "name": quant.location_id.display_name,
            } if quant.location_id else None,
        })
    return data


def _get_product(env, product_id):
    if not product_id:
        raise ValidationError("'product_id' is required.")
    try:
        product_id = int(product_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'product_id' must be a valid integer id.") from exc

    product = env["product.product"].sudo().browse(product_id).exists()
    if not product:
        raise ValidationError("No product was found for the provided 'product_id'.")
    return product

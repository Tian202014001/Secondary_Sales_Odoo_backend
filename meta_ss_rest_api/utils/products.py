# -*- coding: utf-8 -*-

from odoo.osv import expression

from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination, parse_active_filter


def build_product_domain(payload):
    """Build a product.product domain for the mobile product picker."""
    domain = [
        ("sale_ok", "=", True),
        ("active", "=", parse_active_filter(payload)),
    ]

    search = (payload.get("search") or payload.get("name") or "").strip()
    if search:
        search_domain = expression.OR([
            [("name", "ilike", search)],
            [("default_code", "ilike", search)],
            [("barcode", "ilike", search)],
        ])
        domain = expression.AND([domain, search_domain])

    if payload.get("default_code"):
        domain.append(("default_code", "ilike", str(payload.get("default_code"))))
    if payload.get("barcode"):
        domain.append(("barcode", "ilike", str(payload.get("barcode"))))
    if payload.get("type"):
        domain.append(("type", "=", str(payload.get("type"))))
    if payload.get("id"):
        domain.append(("id", "=", int(payload.get("id"))))

    return domain


def get_product_pagination(payload):
    """Return pagination values for product list APIs."""
    return get_pagination(payload)


def serialize_products(products):
    """Serialize product variants for the mobile app."""
    data = []
    for product in products:
        data.append({
            "id": product.id,
            "name": product.display_name,
            "default_code": product.default_code or None,
            "barcode": product.barcode or None,
            "list_price": product.list_price or 0.0,
            "standard_price": product.standard_price or 0.0,
            "uom": {
                "id": product.uom_id.id,
                "name": product.uom_id.name,
            } if product.uom_id else None,
            "uom_name": product.uom_id.name if product.uom_id else None,
            "qty_available": product.qty_available,
            "type": product.type or None,
            "active": product.active,
        })
    return data

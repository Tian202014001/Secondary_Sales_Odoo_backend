# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    mobile_api_error_boundary,
)
from odoo.addons.meta_ss_rest_api.utils.products import (
    build_product_domain,
    get_product_pagination,
    serialize_products,
)


class MetaSSProductController(http.Controller):

    @http.route(f"{API_PREFIX}/products", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_products(self, **payload):
        """Return saleable products for the mobile primary sale flow."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload)
        domain = build_product_domain(payload)
        limit, offset, page, page_size = get_product_pagination(payload)

        Product = api_env["product.product"]
        sale_type = payload.get("sale_type")
        employee_id = payload.get("employee_id")
        distributor_location_id = None

        if sale_type == "secondary" and employee_id:
            employee = api_env["hr.employee"].browse(int(employee_id))
            van_locations = api_env["stock.location"].sudo().search([
                ("ss_location_type", "=", "van_loading"),
                ("ss_employee_id", "child_of", employee.id),
                ("scrap_location", "=", False),
                ("active", "=", True),
            ])
            if van_locations:
                van_location = van_locations[0]
                distributor_location_id = van_location.location_id.id if van_location.location_id else None
                Product = Product.with_context(location=van_location.id)
                # Restrict products to those with available stock in the van
                quants = api_env["stock.quant"].search([
                    ("location_id", "child_of", van_location.id),
                    ("quantity", ">", 0)
                ])
                product_ids = list(set(quants.mapped("product_id").ids))
                domain.append(("id", "in", product_ids))
            else:
                # If no van location, they cannot sell anything
                domain.append(("id", "in", []))
        elif sale_type == "primary" or not sale_type:
            warehouse = api_env["stock.warehouse"].sudo().search([
                ("company_id", "=", api_env.company.id)
            ], limit=1)
            if warehouse and warehouse.lot_stock_id:
                Product = Product.with_context(location=warehouse.lot_stock_id.id)

        partner_id = payload.get("partner_id")
        partner = None
        if partner_id:
            try:
                partner = api_env["res.partner"].sudo().browse(int(partner_id))
                if not partner.exists():
                    partner = None
            except (ValueError, TypeError):
                partner = None

        products = Product.search(domain, limit=limit, offset=offset, order="name")
        total = Product.search_count(domain)
        data = serialize_products(products, partner=partner, distributor_location_id=distributor_location_id)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Products fetched successfully.",
            "data": data,
            "products": data,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }


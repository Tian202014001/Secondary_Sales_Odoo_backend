# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
)
from odoo.addons.meta_ss_rest_api.utils.products import (
    build_product_domain,
    get_product_pagination,
    serialize_products,
)


class MetaSSProductController(http.Controller):

    @http.route(f"{API_PREFIX}/products", type="json", auth="user", methods=["POST"])
    def get_products(self, **payload):
        """Return saleable products for the mobile primary sale flow."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload)
            domain = build_product_domain(payload)
            limit, offset, page, page_size = get_product_pagination(payload)

            Product = api_env["product.product"]
            sale_type = payload.get("sale_type")
            employee_id = payload.get("employee_id")

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

            products = Product.search(domain, limit=limit, offset=offset, order="name")
            total = Product.search_count(domain)
            data = serialize_products(products)

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
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching products.",
            )

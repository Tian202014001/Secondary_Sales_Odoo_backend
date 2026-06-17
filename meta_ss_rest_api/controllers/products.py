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

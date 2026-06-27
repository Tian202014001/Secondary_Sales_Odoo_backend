# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    error_response,
    get_mobile_api_context,
)
from odoo.addons.meta_ss_transfer.utils.returns import (
    build_return_domain,
    build_return_product_domain,
    create_return_delivery,
    serialize_returns,
    serialize_return_delivery,
    serialize_return_prepare,
    serialize_return_product_lots,
    serialize_return_products,
    get_pagination,
    get_return_delivery_for_employee,
    update_return_delivery,
)


class MetaSSReturnController(http.Controller):

    @http.route(f"{API_PREFIX}/returns/prepare", type="json", auth="user", methods=["POST"])
    def prepare_return(self, **payload):
        """Fetch distributor location, destination warehouse, and available stock."""
        try:
            get_mobile_api_context(payload, require_employee=True)
            result = serialize_return_prepare(request.env, payload)
            return {
                "success": True,
                "api_version": "v1",
                "message": "Return context prepared successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while preparing return.")

    @http.route(f"{API_PREFIX}/returns", type="json", auth="user", methods=["POST"])
    def get_returns(self, **payload):
        """Get list of return deliveries."""
        try:
            get_mobile_api_context(payload, require_employee=True)
            domain = build_return_domain(request.env, payload)
            
            limit, offset, _, _ = get_pagination(payload)
            order = payload.get("order", "id desc")
                
            pickings = request.env["stock.picking"].sudo().search(
                domain, limit=limit, offset=offset, order=order
            )
            total_count = request.env["stock.picking"].sudo().search_count(domain)
            
            result = serialize_returns(pickings)
            
            return {
                "success": True,
                "api_version": "v1",
                "message": "Returns fetched successfully.",
                "data": result,
                "meta": {
                    "total": total_count,
                    "limit": limit,
                    "offset": offset,
                },
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while fetching returns.")

    @http.route(f"{API_PREFIX}/returns/products", type="json", auth="user", methods=["POST"])
    def get_return_products(self, **payload):
        """Get available products for return from distributor customer location."""
        try:
            get_mobile_api_context(payload, require_employee=True)
            source_location, domain = build_return_product_domain(request.env, payload)
            
            products = request.env["product.product"].sudo().search(domain, order="name")
            result = serialize_return_products(request.env, products, source_location)
            
            return {
                "success": True,
                "api_version": "v1",
                "message": "Return products fetched successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while fetching return products.")

    @http.route(f"{API_PREFIX}/returns/products/<int:product_id>/lots", type="json", auth="user", methods=["POST"])
    def get_return_product_lots(self, product_id, **payload):
        """Get available lots for a product in distributor customer location."""
        try:
            get_mobile_api_context(payload, require_employee=True)
            result = serialize_return_product_lots(request.env, payload, product_id)
            return {
                "success": True,
                "api_version": "v1",
                "message": "Return product lots fetched successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while fetching return product lots.")

    @http.route(f"{API_PREFIX}/returns/create", type="json", auth="user", methods=["POST"])
    def create_return(self, **payload):
        """Create a return picking from distributor customer location to warehouse."""
        try:
            get_mobile_api_context(payload, require_employee=True)
            picking = create_return_delivery(request.env, payload)
            result = serialize_return_delivery(picking)
            
            return {
                "success": True,
                "api_version": "v1",
                "message": "Return delivery created successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while creating return.")

    @http.route(f"{API_PREFIX}/returns/<int:picking_id>", type="json", auth="user", methods=["POST"])
    def get_return_details(self, picking_id, **payload):
        """Get details of a specific return delivery."""
        try:
            get_mobile_api_context(payload, require_employee=True)
            picking = get_return_delivery_for_employee(request.env, picking_id, payload)
            result = serialize_return_delivery(picking)
            return {
                "success": True,
                "api_version": "v1",
                "message": "Return delivery fetched successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while fetching return details.")

    @http.route(f"{API_PREFIX}/returns/<int:picking_id>/update", type="json", auth="user", methods=["POST"])
    def update_return(self, picking_id, **payload):
        """Update lines of an existing draft/assigned return delivery."""
        try:
            get_mobile_api_context(payload, require_employee=True)
            picking = update_return_delivery(request.env, picking_id, payload)
            result = serialize_return_delivery(picking)
            return {
                "success": True,
                "api_version": "v1",
                "message": "Return delivery updated successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while updating return.")

# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    error_response,
    get_mobile_api_context,
)
from odoo.addons.meta_ss_transfer.utils.scraps import (
    build_scrap_domain,
    build_scrap_product_domain,
    create_scrap_delivery,
    serialize_scraps,
    serialize_scrap_delivery,
    serialize_scrap_prepare,
    serialize_scrap_product_lots,
    serialize_scrap_products,
    get_scrap_delivery_for_employee,
    update_scrap_delivery,
)
from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination


class MetaSSScrapController(http.Controller):

    @http.route(f"{API_PREFIX}/scraps/prepare", type="json", auth="user", methods=["POST"])
    def prepare_scrap(self, **payload):
        """Fetch distributor scrap location, destination scrap location, and available stock."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            result = serialize_scrap_prepare(api_env, payload)
            return {
                "success": True,
                "api_version": "v1",
                "message": "Scrap context prepared successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while preparing scrap.")

    @http.route(f"{API_PREFIX}/scraps", type="json", auth="user", methods=["POST"])
    def get_scraps(self, **payload):
        """Get list of scrap deliveries."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            domain = build_scrap_domain(api_env, payload)
            
            limit, offset, _, _ = get_pagination(payload)
            order = payload.get("order", "id desc")
                
            pickings = api_env["stock.picking"].sudo().search(
                domain, limit=limit, offset=offset, order=order
            )
            total_count = api_env["stock.picking"].sudo().search_count(domain)
            
            result = serialize_scraps(pickings)
            
            return {
                "success": True,
                "api_version": "v1",
                "message": "Scraps fetched successfully.",
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
            return error_response("server_error", "An unexpected error occurred while fetching scraps.")

    @http.route(f"{API_PREFIX}/scraps/products", type="json", auth="user", methods=["POST"])
    def get_scrap_products(self, **payload):
        """Get available products for scrap from distributor scrap location."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            source_location, domain = build_scrap_product_domain(api_env, payload)
            
            products = api_env["product.product"].sudo().search(domain, order="name")
            result = serialize_scrap_products(api_env, products, source_location)
            
            return {
                "success": True,
                "api_version": "v1",
                "message": "Scrap products fetched successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while fetching scrap products.")

    @http.route(f"{API_PREFIX}/scraps/products/<int:product_id>/lots", type="json", auth="user", methods=["POST"])
    def get_scrap_product_lots(self, product_id, **payload):
        """Get available lots for a product in distributor scrap location."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            result = serialize_scrap_product_lots(api_env, payload, product_id)
            return {
                "success": True,
                "api_version": "v1",
                "message": "Scrap product lots fetched successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while fetching scrap product lots.")

    @http.route(f"{API_PREFIX}/scraps/create", type="json", auth="user", methods=["POST"])
    def create_scrap(self, **payload):
        """Create a scrap picking from distributor scrap location to virtual scrap location."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            picking = create_scrap_delivery(api_env, payload)
            result = serialize_scrap_delivery(picking)
            
            return {
                "success": True,
                "api_version": "v1",
                "message": "Scrap delivery created successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while creating scrap.")

    @http.route(f"{API_PREFIX}/scraps/<int:picking_id>", type="json", auth="user", methods=["POST"])
    def get_scrap_details(self, picking_id, **payload):
        """Get details of a specific scrap delivery."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            picking = get_scrap_delivery_for_employee(api_env, picking_id, payload)
            result = serialize_scrap_delivery(picking)
            return {
                "success": True,
                "api_version": "v1",
                "message": "Scrap delivery fetched successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while fetching scrap details.")

    @http.route(f"{API_PREFIX}/scraps/<int:picking_id>/update", type="json", auth="user", methods=["POST"])
    def update_scrap(self, picking_id, **payload):
        """Update lines of an existing draft/assigned scrap delivery."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            picking = update_scrap_delivery(api_env, picking_id, payload)
            result = serialize_scrap_delivery(picking)
            return {
                "success": True,
                "api_version": "v1",
                "message": "Scrap delivery updated successfully.",
                "data": result,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response("server_error", "An unexpected error occurred while updating scrap.")

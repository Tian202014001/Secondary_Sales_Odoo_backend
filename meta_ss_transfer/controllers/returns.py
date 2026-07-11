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
    validate_return_delivery,
    cancel_return_delivery,
)


class MetaSSReturnController(http.Controller):

    @http.route(f"{API_PREFIX}/returns/prepare", type="json", auth="user", methods=["POST"])
    def prepare_return(self, **payload):
        """Fetch distributor location, destination warehouse, and available stock."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            result = serialize_return_prepare(api_env, payload)
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
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            domain = build_return_domain(api_env, payload)
            
            limit, offset, _, _ = get_pagination(payload)
            order = payload.get("order", "id desc")
                
            pickings = api_env["stock.picking"].sudo().search(
                domain, limit=limit, offset=offset, order=order
            )
            total_count = api_env["stock.picking"].sudo().search_count(domain)
            
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
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            source_location, domain = build_return_product_domain(api_env, payload)
            
            products = api_env["product.product"].sudo().search(domain, order="name")
            result = serialize_return_products(api_env, products, source_location)
            
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
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            result = serialize_return_product_lots(api_env, payload, product_id)
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
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            picking = create_return_delivery(api_env, payload)
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
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            picking = get_return_delivery_for_employee(api_env, picking_id, payload)
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
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            picking = update_return_delivery(api_env, picking_id, payload)
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

    @http.route(f"{API_PREFIX}/returns/<int:picking_id>/action", type="json", auth="user", methods=["POST"])
    def return_action(self, picking_id, **payload):
        """Run a return transfer action such as validate or cancel."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            action = (payload.get("action") or "").strip().lower()
            if action == "validate":
                picking, result = validate_return_delivery(api_env, picking_id, payload)
                return {
                    "success": True,
                    "api_version": "v1",
                    "message": "Return delivery validated successfully.",
                    "data": {
                        "validation_result": True if result is True else result,
                        "transfer": serialize_return_delivery(picking),
                    },
                }
            if action == "cancel":
                picking = cancel_return_delivery(api_env, picking_id, payload)
                return {
                    "success": True,
                    "api_version": "v1",
                    "message": "Return delivery cancelled successfully.",
                    "data": serialize_return_delivery(picking),
                }
            raise ValidationError("Unsupported return action '%s'." % action)
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while running the return action.",
            )


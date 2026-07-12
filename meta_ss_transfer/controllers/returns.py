# -*- coding: utf-8 -*-

from odoo import http
from odoo.http import request
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    mobile_api_error_boundary,
    require_sale_type_access,
)
from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey
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
    @mobile_api_error_boundary
    def prepare_return(self, **payload):
        """Fetch distributor location, destination warehouse, and available stock."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_RETURNS_CREATE,
            AccessKey.SECONDARY_RETURNS_CREATE,
        )
        result = serialize_return_prepare(api_env, payload)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Return context prepared successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/returns", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_returns(self, **payload):
        """Get list of return deliveries."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_RETURNS_LIST,
            AccessKey.SECONDARY_RETURNS_LIST,
        )
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
            "api_version": API_VERSION,
            "message": "Returns fetched successfully.",
            "data": result,
            "meta": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
            },
        }

    @http.route(f"{API_PREFIX}/returns/products", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_return_products(self, **payload):
        """Get available products for return from distributor customer location."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_RETURNS_CREATE,
            AccessKey.SECONDARY_RETURNS_CREATE,
        )
        source_location, domain = build_return_product_domain(api_env, payload)

        products = api_env["product.product"].sudo().search(domain, order="name")
        result = serialize_return_products(api_env, products, source_location)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Return products fetched successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/returns/products/<int:product_id>/lots", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_return_product_lots(self, product_id, **payload):
        """Get available lots for a product in distributor customer location."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_RETURNS_CREATE,
            AccessKey.SECONDARY_RETURNS_CREATE,
        )
        result = serialize_return_product_lots(api_env, payload, product_id)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Return product lots fetched successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/returns/create", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def create_return(self, **payload):
        """Create a return picking from distributor customer location to warehouse."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_RETURNS_CREATE,
            AccessKey.SECONDARY_RETURNS_CREATE,
        )
        picking = create_return_delivery(api_env, payload)
        result = serialize_return_delivery(picking)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Return delivery created successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/returns/<int:picking_id>", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_return_details(self, picking_id, **payload):
        """Get details of a specific return delivery."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_RETURNS_LIST,
            AccessKey.SECONDARY_RETURNS_LIST,
        )
        picking = get_return_delivery_for_employee(api_env, picking_id, payload)
        result = serialize_return_delivery(picking)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Return delivery fetched successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/returns/<int:picking_id>/update", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def update_return(self, picking_id, **payload):
        """Update lines of an existing draft/assigned return delivery."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_RETURNS_SAVE,
            AccessKey.SECONDARY_RETURNS_SAVE,
        )
        picking = update_return_delivery(api_env, picking_id, payload)
        result = serialize_return_delivery(picking)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Return delivery updated successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/returns/<int:picking_id>/action", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def return_action(self, picking_id, **payload):
        """Run a return transfer action such as validate or cancel."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        action = (payload.get("action") or "").strip().lower()
        if action == "validate":
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_RETURNS_VALIDATE,
                AccessKey.SECONDARY_RETURNS_VALIDATE,
            )
        elif action == "cancel":
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_RETURNS_CANCEL,
                AccessKey.SECONDARY_RETURNS_CANCEL,
            )
        else:
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_RETURNS_SAVE,
                AccessKey.SECONDARY_RETURNS_SAVE,
            )
        if action == "validate":
            picking, result = validate_return_delivery(api_env, picking_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
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
                "api_version": API_VERSION,
                "message": "Return delivery cancelled successfully.",
                "data": serialize_return_delivery(picking),
            }
        raise ValidationError("Unsupported return action '%s'." % action)


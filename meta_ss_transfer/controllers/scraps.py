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
    validate_scrap_delivery,
    cancel_scrap_delivery,
)
from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination


class MetaSSScrapController(http.Controller):

    @http.route(f"{API_PREFIX}/scraps/prepare", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def prepare_scrap(self, **payload):
        """Fetch distributor scrap location, destination scrap location, and available stock."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_SCRAPS_CREATE,
            AccessKey.SECONDARY_SCRAPS_CREATE,
        )
        result = serialize_scrap_prepare(api_env, payload)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Scrap context prepared successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/scraps", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_scraps(self, **payload):
        """Get list of scrap deliveries."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_SCRAPS_LIST,
            AccessKey.SECONDARY_SCRAPS_LIST,
        )
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
            "api_version": API_VERSION,
            "message": "Scraps fetched successfully.",
            "data": result,
            "meta": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
            },
        }

    @http.route(f"{API_PREFIX}/scraps/products", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_scrap_products(self, **payload):
        """Get available products for scrap from distributor scrap location."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_SCRAPS_CREATE,
            AccessKey.SECONDARY_SCRAPS_CREATE,
        )
        source_location, domain = build_scrap_product_domain(api_env, payload)

        products = api_env["product.product"].sudo().search(domain, order="name")
        result = serialize_scrap_products(api_env, products, source_location)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Scrap products fetched successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/scraps/products/<int:product_id>/lots", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_scrap_product_lots(self, product_id, **payload):
        """Get available lots for a product in distributor scrap location."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_SCRAPS_CREATE,
            AccessKey.SECONDARY_SCRAPS_CREATE,
        )
        result = serialize_scrap_product_lots(api_env, payload, product_id)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Scrap product lots fetched successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/scraps/create", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def create_scrap(self, **payload):
        """Create a scrap picking from distributor scrap location to virtual scrap location."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_SCRAPS_CREATE,
            AccessKey.SECONDARY_SCRAPS_CREATE,
        )
        picking = create_scrap_delivery(api_env, payload)
        result = serialize_scrap_delivery(picking)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Scrap delivery created successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/scraps/<int:picking_id>", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_scrap_details(self, picking_id, **payload):
        """Get details of a specific scrap delivery."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_SCRAPS_LIST,
            AccessKey.SECONDARY_SCRAPS_LIST,
        )
        picking = get_scrap_delivery_for_employee(api_env, picking_id, payload)
        result = serialize_scrap_delivery(picking)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Scrap delivery fetched successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/scraps/<int:picking_id>/update", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def update_scrap(self, picking_id, **payload):
        """Update lines of an existing draft/assigned scrap delivery."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_SCRAPS_SAVE,
            AccessKey.SECONDARY_SCRAPS_SAVE,
        )
        picking = update_scrap_delivery(api_env, picking_id, payload)
        result = serialize_scrap_delivery(picking)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Scrap delivery updated successfully.",
            "data": result,
        }

    @http.route(f"{API_PREFIX}/scraps/<int:picking_id>/action", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def scrap_action(self, picking_id, **payload):
        """Run a scrap transfer action such as validate or cancel."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        action = (payload.get("action") or "").strip().lower()
        if action == "validate":
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_SCRAPS_VALIDATE,
                AccessKey.SECONDARY_SCRAPS_VALIDATE,
            )
        elif action == "cancel":
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_SCRAPS_CANCEL,
                AccessKey.SECONDARY_SCRAPS_CANCEL,
            )
        else:
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_SCRAPS_SAVE,
                AccessKey.SECONDARY_SCRAPS_SAVE,
            )
        if action == "validate":
            picking, result = validate_scrap_delivery(api_env, picking_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Scrap delivery validated successfully.",
                "data": {
                    "validation_result": True if result is True else result,
                    "transfer": serialize_scrap_delivery(picking),
                },
            }
        if action == "cancel":
            picking = cancel_scrap_delivery(api_env, picking_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Scrap delivery cancelled successfully.",
                "data": serialize_scrap_delivery(picking),
            }
        raise ValidationError("Unsupported scrap action '%s'." % action)


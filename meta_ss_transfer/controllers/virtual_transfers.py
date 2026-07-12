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
    require_ui_access,
)
from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey
from odoo.addons.meta_ss_transfer.utils.virtual_transfers import (
    build_virtual_transfer_domain,
    build_virtual_transfer_product_domain,
    cancel_virtual_transfer,
    create_virtual_transfer,
    get_virtual_transfer_for_employee,
    get_virtual_transfer_pagination,
    serialize_product_lots,
    serialize_transfer_products,
    serialize_virtual_transfer,
    serialize_virtual_transfer_prepare,
    validate_virtual_transfer,
    update_virtual_transfer,
)


class MetaSSVirtualTransferController(http.Controller):

    def _run_virtual_transfer_action(self, api_env, transfer_id, payload):
        action = (payload.get("action") or "").strip().lower()
        if action == "validate":
            picking, result = validate_virtual_transfer(api_env, transfer_id, payload)
            return {
                "message": "Virtual transfer validated successfully.",
                "data": {
                    "validation_result": True if result is True else result,
                    "transfer": serialize_virtual_transfer(picking),
                },
            }
        if action == "cancel":
            picking = cancel_virtual_transfer(api_env, transfer_id, payload)
            return {
                "message": "Virtual transfer cancelled successfully.",
                "data": serialize_virtual_transfer(picking),
            }
        raise ValidationError("Unsupported virtual transfer action '%s'." % action)

    @http.route(f"{API_PREFIX}/virtual-transfers/prepare", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def prepare_virtual_transfer(self, **payload):
        """Prepare distributor source and employee Van Loading destinations.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7
                },
                "id": 1
            }

        Response body example:
            {
                "success": true,
                "api_version": API_VERSION,
                "message": "Virtual transfer data fetched successfully.",
                "data": {
                    "employee": {"id": 7, "name": "Audrey Peterson"},
                    "distributor": {"id": 3, "name": "Distributor A"},
                    "source_location": {"id": 5, "name": "Partners/Customers"},
                    "destination_locations": [
                        {
                            "id": 48,
                            "name": "Van Loading 1",
                            "location_type": "van_loading"
                        }
                    ]
                }
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_CREATE)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Virtual transfer data fetched successfully.",
            "data": serialize_virtual_transfer_prepare(api_env, payload),
        }

    @http.route(f"{API_PREFIX}/virtual-transfers/products", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_virtual_transfer_products(self, **payload):
        """Search products available in the employee distributor customer location.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "search": "Milk",
                    "page": 1,
                    "page_size": 20
                },
                "id": 1
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_CREATE)
        source_location, domain = build_virtual_transfer_product_domain(api_env, payload)
        limit, offset, page, page_size = get_virtual_transfer_pagination(payload)
        Product = api_env["product.product"]
        products = Product.search(domain, limit=limit, offset=offset, order="name")
        total = Product.search_count(domain)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Transfer products fetched successfully.",
            "source_location": {
                "id": source_location.id,
                "name": source_location.display_name,
                "usage": source_location.usage,
            },
            "data": serialize_transfer_products(api_env, products, source_location, payload=payload),
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }

    @http.route(
        f"{API_PREFIX}/virtual-transfers/products/<int:product_id>/lots",
        type="json",
        auth="user",
        methods=["POST"],
    )
    @mobile_api_error_boundary
    def get_virtual_transfer_product_lots(self, product_id, **payload):
        """Return lot-wise available stock in the distributor customer location."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_CREATE)
        data = serialize_product_lots(api_env, payload, product_id)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Transfer product lots fetched successfully.",
            **data,
        }

    @http.route(
        f"{API_PREFIX}/virtual-transfers/products/<int:product_id>/auto-assign-lots",
        type="json",
        auth="user",
        methods=["POST"],
    )
    @mobile_api_error_boundary
    def get_virtual_transfer_auto_assign_lots(self, product_id, **payload):
        """Return auto-assigned (FIFO) lot lines for a given quantity in the distributor location."""
        from odoo.addons.meta_ss_rest_api.utils.helpers import _auto_assign_lots, _get_positive_float
        from odoo.addons.meta_ss_transfer.utils.virtual_transfers import get_employee_transfer_context, _get_product

        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_CREATE)
        _employee, _distributor, source_location = get_employee_transfer_context(api_env, payload)
        product = _get_product(api_env, product_id)
        quantity = _get_positive_float(payload.get("quantity"), "quantity")

        lot_lines = _auto_assign_lots(api_env, product, quantity, source_location)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Lots auto-assigned successfully.",
            "data": lot_lines,
        }

    @http.route(f"{API_PREFIX}/virtual-transfers/create", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def create_van_loading_transfer(self, **payload):
        """Create a Virtual Location Transfer into an assigned Van Loading Location.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "destination_location_id": 48,
                    "lines": [
                        {"product_id": 25, "quantity": 2.0}
                    ]
                },
                "id": 1
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_CREATE)
        picking = create_virtual_transfer(api_env, payload)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Virtual transfer created successfully.",
            "data": serialize_virtual_transfer(picking),
        }

    @http.route(f"{API_PREFIX}/virtual-transfers", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_virtual_transfers(self, **payload):
        """List virtual transfers for the employee's assigned distributor."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_LIST)
        domain = build_virtual_transfer_domain(api_env, payload)
        limit, offset, page, page_size = get_virtual_transfer_pagination(payload)
        Picking = api_env["stock.picking"]
        transfers = Picking.search(domain, limit=limit, offset=offset, order="scheduled_date desc, id desc")
        total = Picking.search_count(domain)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Virtual transfers fetched successfully.",
            "data": [serialize_virtual_transfer(transfer) for transfer in transfers],
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
            },
        }

    @http.route(f"{API_PREFIX}/virtual-transfers/<int:transfer_id>", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_virtual_transfer_detail(self, transfer_id, **payload):
        """Return one virtual transfer detail."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_DETAIL)
        picking = get_virtual_transfer_for_employee(api_env, transfer_id, payload)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Virtual transfer fetched successfully.",
            "data": serialize_virtual_transfer(picking),
        }

    @http.route(f"{API_PREFIX}/virtual-transfers/<int:transfer_id>/update", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def update_virtual_transfer(self, transfer_id, **payload):
        """Update lines of an existing draft/assigned virtual transfer."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_CREATE)
        picking = update_virtual_transfer(api_env, transfer_id, payload)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Virtual transfer updated successfully.",
            "data": serialize_virtual_transfer(picking),
        }

    @http.route(f"{API_PREFIX}/virtual-transfers/<int:transfer_id>/action", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def virtual_transfer_action(self, transfer_id, **payload):
        """Run a virtual transfer action such as validate or cancel."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        action = (payload.get("action") or "").strip().lower()
        if action == "validate":
            require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_VALIDATE)
        elif action == "cancel":
            require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_CANCEL)
        else:
            require_ui_access(_mobile_user, AccessKey.SECONDARY_TRANSFERS_CREATE)
        result = self._run_virtual_transfer_action(api_env, transfer_id, payload)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": result["message"],
            "data": result["data"],
        }


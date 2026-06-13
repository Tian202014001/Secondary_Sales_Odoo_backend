# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import API_PREFIX, API_VERSION, error_response
from odoo.addons.meta_ss_rest_api.utils.virtual_transfers import (
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
)


class MetaSSVirtualTransferController(http.Controller):

    def _run_virtual_transfer_action(self, transfer_id, payload):
        action = (payload.get("action") or "").strip().lower()
        if action == "validate":
            picking, result = validate_virtual_transfer(request.env, transfer_id, payload)
            return {
                "message": "Virtual transfer validated successfully.",
                "data": {
                    "validation_result": True if result is True else result,
                    "transfer": serialize_virtual_transfer(picking),
                },
            }
        if action == "cancel":
            picking = cancel_virtual_transfer(request.env, transfer_id, payload)
            return {
                "message": "Virtual transfer cancelled successfully.",
                "data": serialize_virtual_transfer(picking),
            }
        raise ValidationError("Unsupported virtual transfer action '%s'." % action)

    @http.route(f"{API_PREFIX}/virtual-transfers/prepare", type="json", auth="public", methods=["POST"])
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
                "api_version": "v1",
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
        try:
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Virtual transfer data fetched successfully.",
                "data": serialize_virtual_transfer_prepare(request.env, payload),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while preparing virtual transfer data.",
            )

    @http.route(f"{API_PREFIX}/virtual-transfers/products", type="json", auth="public", methods=["POST"])
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
        try:
            source_location, domain = build_virtual_transfer_product_domain(request.env, payload)
            limit, offset, page, page_size = get_virtual_transfer_pagination(payload)
            Product = request.env["product.product"].sudo()
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
                "data": serialize_transfer_products(request.env, products, source_location),
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                },
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching transfer products.",
            )

    @http.route(
        f"{API_PREFIX}/virtual-transfers/products/<int:product_id>/lots",
        type="json",
        auth="public",
        methods=["POST"],
    )
    def get_virtual_transfer_product_lots(self, product_id, **payload):
        """Return lot-wise available stock in the distributor customer location."""
        try:
            data = serialize_product_lots(request.env, payload, product_id)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Transfer product lots fetched successfully.",
                **data,
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching transfer product lots.",
            )

    @http.route(
        f"{API_PREFIX}/virtual-transfers/products/<int:product_id>/auto-assign-lots",
        type="json",
        auth="public",
        methods=["POST"],
    )
    def get_virtual_transfer_auto_assign_lots(self, product_id, **payload):
        """Return auto-assigned (FIFO) lot lines for a given quantity in the distributor location."""
        try:
            from odoo.addons.meta_ss_rest_api.utils.helpers import _auto_assign_lots, _get_positive_float
            from odoo.addons.meta_ss_rest_api.utils.virtual_transfers import get_employee_transfer_context, _get_product

            _employee, _distributor, source_location = get_employee_transfer_context(request.env, payload)
            product = _get_product(request.env, product_id)
            quantity = _get_positive_float(payload.get("quantity"), "quantity")
            
            lot_lines = _auto_assign_lots(request.env, product, quantity, source_location)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Lots auto-assigned successfully.",
                "data": lot_lines,
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while auto-assigning lots.",
            )

    @http.route(f"{API_PREFIX}/virtual-transfers/create", type="json", auth="public", methods=["POST"])
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
        try:
            picking = create_virtual_transfer(request.env, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Virtual transfer created successfully.",
                "data": serialize_virtual_transfer(picking),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while creating the virtual transfer.",
            )

    @http.route(f"{API_PREFIX}/virtual-transfers", type="json", auth="public", methods=["POST"])
    def get_virtual_transfers(self, **payload):
        """List virtual transfers for the employee's assigned distributor."""
        try:
            domain = build_virtual_transfer_domain(request.env, payload)
            limit, offset, page, page_size = get_virtual_transfer_pagination(payload)
            Picking = request.env["stock.picking"].sudo()
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
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching virtual transfers.",
            )

    @http.route(f"{API_PREFIX}/virtual-transfers/<int:transfer_id>", type="json", auth="public", methods=["POST"])
    def get_virtual_transfer_detail(self, transfer_id, **payload):
        """Return one virtual transfer detail."""
        try:
            picking = get_virtual_transfer_for_employee(request.env, transfer_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Virtual transfer fetched successfully.",
                "data": serialize_virtual_transfer(picking),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching the virtual transfer.",
            )

    @http.route(f"{API_PREFIX}/virtual-transfers/<int:transfer_id>/action", type="json", auth="public", methods=["POST"])
    def virtual_transfer_action(self, transfer_id, **payload):
        """Run a virtual transfer action such as validate or cancel."""
        try:
            result = self._run_virtual_transfer_action(transfer_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": result["message"],
                "data": result["data"],
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while running the virtual transfer action.",
            )

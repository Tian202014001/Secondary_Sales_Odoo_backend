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
from odoo.addons.meta_ss_sales.utils.deliveries import (
    get_delivery_context_by_payload,
    get_delivery_context_by_picking,
    perform_delivery_action,
    resolve_delivery_location,
    serialize_delivery_prepare,
    build_delivery_domain,
    get_delivery_pagination,
    serialize_delivery_list_item,
)


class MetaSSDeliveryController(http.Controller):

    @http.route(
        f"{API_PREFIX}/deliveries",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def get_deliveries(self, **payload):
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            domain = build_delivery_domain(payload)
            limit, offset, page, page_size = get_delivery_pagination(payload)

            Picking = api_env["stock.picking"]
            pickings = Picking.search(domain, limit=limit, offset=offset, order="scheduled_date desc, id desc")
            total = Picking.search_count(domain)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Deliveries fetched successfully.",
                "data": [serialize_delivery_list_item(p) for p in pickings],
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
                "An unexpected error occurred while fetching deliveries.",
            )

    @http.route(
        f"{API_PREFIX}/deliveries/prepare",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def prepare_delivery(self, **payload):
        """Return data needed by the mobile delivery validation screen.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "sale_order_id": 20,
                    "picking_id": 12
                },
                "id": 1
            }
        """
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            order, picking = get_delivery_context_by_payload(api_env, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Delivery validation data fetched successfully.",
                "data": serialize_delivery_prepare(api_env, order, picking),
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while preparing delivery validation.",
            )

    @http.route(
        f"{API_PREFIX}/deliveries/products/<int:product_id>/lots",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def get_delivery_product_lots(self, product_id, **payload):
        """Return lot-wise available stock in the delivery's source location.

        'location_id' is sufficient. 'sale_order_id' is only needed as a fallback
        when no location is provided, to derive the picking's source location.
        """
        try:
            from odoo.addons.meta_ss_transfer.utils.virtual_transfers import _get_product, _serialize_product, _serialize_location

            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            location = resolve_delivery_location(api_env, payload)
            if location is None:
                _, picking = get_delivery_context_by_payload(api_env, payload)
                location = picking.location_id

            if not location:
                raise ValidationError("Source location is missing. Provide 'location_id' or 'sale_order_id'.")

            product = _get_product(api_env, product_id)
            
            quants = api_env["stock.quant"].search([
                ("product_id", "=", product.id),
                ("location_id", "child_of", location.id),
                ("lot_id", "!=", False),
            ])

            # Group quants by lot_id and sum quantities
            lot_data_map = {}
            for quant in quants:
                lot_id = quant.lot_id.id
                if lot_id not in lot_data_map:
                    lot_data_map[lot_id] = {
                        "lot_id": lot_id,
                        "lot_name": quant.lot_id.name,
                        "available_qty": 0.0,
                        "quantity": 0.0,
                        "reserved_quantity": 0.0,
                        "uom": {
                            "id": quant.product_uom_id.id,
                            "name": quant.product_uom_id.name,
                        } if quant.product_uom_id else None,
                        "location": _serialize_location(location),
                    }
                
                lot_data_map[lot_id]["available_qty"] += quant.available_quantity
                lot_data_map[lot_id]["quantity"] += quant.quantity
                lot_data_map[lot_id]["reserved_quantity"] += quant.reserved_quantity

            # Filter out lots that have no available stock
            valid_lots = [data for data in lot_data_map.values() if data["available_qty"] > 0]

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Delivery product lots fetched successfully.",
                "product": _serialize_product(product),
                "source_location": _serialize_location(location),
                "data": sorted(valid_lots, key=lambda x: x["lot_name"] or ""),
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching delivery product lots.",
            )

    @http.route(
        f"{API_PREFIX}/deliveries/products/<int:product_id>/auto-assign-lots",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def get_delivery_auto_assign_lots(self, product_id, **payload):
        """Return auto-assigned (FIFO) lot lines for a given quantity.

        'location_id' is sufficient. 'sale_order_id' is only needed as a fallback
        when no location is provided, to derive the picking's source location.
        """
        try:
            from odoo.addons.meta_ss_rest_api.utils.helpers import _auto_assign_lots, _get_positive_float
            from odoo.addons.meta_ss_transfer.utils.virtual_transfers import _get_product

            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            # Always resolve the picking so its reservations can be treated as
            # available for re-allocation during FIFO (reservation-aware FIFO).
            picking = None
            raw_picking_id = payload.get("picking_id")
            if raw_picking_id:
                _order, picking = get_delivery_context_by_picking(api_env, raw_picking_id, payload)

            location = resolve_delivery_location(api_env, payload)
            if location is None:
                if picking:
                    location = picking.location_id
                else:
                    _, ctx_picking = get_delivery_context_by_payload(api_env, payload)
                    picking = ctx_picking
                    location = picking.location_id

            if not location:
                raise ValidationError("Source location is missing. Provide 'location_id' or 'sale_order_id'.")

            product = _get_product(api_env, product_id)
            quantity = _get_positive_float(payload.get("quantity"), "quantity")

            lot_lines = _auto_assign_lots(api_env, product, quantity, location, picking=picking)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Lots auto-assigned successfully.",
                "data": lot_lines,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while auto-assigning lots.",
            )

    @http.route(
        f"{API_PREFIX}/deliveries/<int:picking_id>/action",
        type="json",
        auth="user",
        methods=["POST"],
    )
    def delivery_action(self, picking_id, **payload):
        """Run a delivery action such as validate or cancel."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            data = perform_delivery_action(api_env, picking_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Delivery action completed successfully.",
                "data": data,
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while running the delivery action.",
            )

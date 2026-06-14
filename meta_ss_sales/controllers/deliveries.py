# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import API_PREFIX, API_VERSION, error_response
from odoo.addons.meta_ss_sales.utils.deliveries import (
    get_delivery_context_by_payload,
    perform_delivery_action,
    resolve_delivery_location,
    serialize_delivery_prepare,
)


class MetaSSDeliveryController(http.Controller):

    @http.route(
        f"{API_PREFIX}/deliveries/prepare",
        type="json",
        auth="public",
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
            order, picking = get_delivery_context_by_payload(request.env, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Delivery validation data fetched successfully.",
                "data": serialize_delivery_prepare(request.env, order, picking),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
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
        auth="public",
        methods=["POST"],
    )
    def get_delivery_product_lots(self, product_id, **payload):
        """Return lot-wise available stock in the delivery's source location.

        'location_id' is sufficient. 'sale_order_id' is only needed as a fallback
        when no location is provided, to derive the picking's source location.
        """
        try:
            from odoo.addons.meta_ss_transfer.utils.virtual_transfers import _get_product, _serialize_product, _serialize_location

            location = resolve_delivery_location(request.env, payload)
            if location is None:
                _, picking = get_delivery_context_by_payload(request.env, payload)
                location = picking.location_id

            if not location:
                raise ValidationError("Source location is missing. Provide 'location_id' or 'sale_order_id'.")

            product = _get_product(request.env, product_id)
            
            quants = request.env["stock.quant"].sudo().search([
                ("product_id", "=", product.id),
                ("location_id", "child_of", location.id),
                ("available_quantity", ">", 0),
                ("lot_id", "!=", False),
            ], order="lot_id")

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Delivery product lots fetched successfully.",
                "product": _serialize_product(product),
                "source_location": _serialize_location(location),
                "data": [
                    {
                        "lot_id": quant.lot_id.id,
                        "lot_name": quant.lot_id.name,
                        "available_qty": quant.available_quantity,
                        "quantity": quant.quantity,
                        "reserved_quantity": quant.reserved_quantity,
                        "uom": {
                            "id": quant.product_uom_id.id,
                            "name": quant.product_uom_id.name,
                        } if quant.product_uom_id else None,
                        "location": _serialize_location(quant.location_id),
                    }
                    for quant in quants
                ],
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
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
        auth="public",
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

            # Always resolve the picking so its reservations can be treated as
            # available for re-allocation during FIFO (reservation-aware FIFO).
            picking = None
            raw_picking_id = payload.get("picking_id")
            if raw_picking_id:
                try:
                    picking = request.env["stock.picking"].sudo().browse(int(raw_picking_id)).exists() or None
                except (TypeError, ValueError):
                    pass

            location = resolve_delivery_location(request.env, payload)
            if location is None:
                if picking:
                    location = picking.location_id
                else:
                    _, ctx_picking = get_delivery_context_by_payload(request.env, payload)
                    picking = ctx_picking
                    location = picking.location_id

            if not location:
                raise ValidationError("Source location is missing. Provide 'location_id' or 'sale_order_id'.")

            product = _get_product(request.env, product_id)
            quantity = _get_positive_float(payload.get("quantity"), "quantity")

            lot_lines = _auto_assign_lots(request.env, product, quantity, location, picking=picking)
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

    @http.route(
        f"{API_PREFIX}/deliveries/<int:picking_id>/action",
        type="json",
        auth="public",
        methods=["POST"],
    )
    def delivery_action(self, picking_id, **payload):
        """Run a delivery action such as validate or cancel."""
        try:
            data = perform_delivery_action(request.env, picking_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Delivery action completed successfully.",
                "data": data,
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while running the delivery action.",
            )

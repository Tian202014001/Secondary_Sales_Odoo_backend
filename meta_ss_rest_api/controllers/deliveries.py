# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import API_PREFIX, API_VERSION, error_response
from odoo.addons.meta_ss_rest_api.utils.deliveries import (
    get_delivery_context_by_payload,
    perform_delivery_action,
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

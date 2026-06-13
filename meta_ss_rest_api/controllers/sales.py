# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import API_PREFIX, API_VERSION, error_response, check_api_permission
from odoo.addons.meta_ss_rest_api.utils.sales import (
    build_sale_order_domain,
    get_sales_pagination,
    parse_bool,
    prepare_sale_order_values,
    serialize_sale_order,
    get_distributor,
    _prepare_sale_order_line_commands,
    update_sale_order_lines,
    _get_int,
)


class MetaSSSalesController(http.Controller):

    @http.route(f"{API_PREFIX}/sale-orders", type="json", auth="public", methods=["POST"])
    def get_sale_orders(self, **payload):
        """Return sale orders filtered by sale_type and common dashboard filters."""
        try:
            domain = build_sale_order_domain(payload)
            limit, offset, page, page_size = get_sales_pagination(payload)

            SaleOrder = request.env["sale.order"].sudo()
            orders = SaleOrder.search(domain, limit=limit, offset=offset, order="date_order desc, id desc")
            total = SaleOrder.search_count(domain)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Sale orders fetched successfully.",
                "data": [serialize_sale_order(order) for order in orders],
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
                "An unexpected error occurred while fetching sale orders.",
            )

    @http.route(f"{API_PREFIX}/sale-orders/create", type="json", auth="public", methods=["POST"])
    def create_sale_order(self, **payload):
        """Create a sale order using sale_type.

        Currently only sale_type='primary' is supported for creation.
        """
        try:
            sale_type = (payload.get("sale_type") or "primary").strip()
            if sale_type != "primary":
                # TODO: Implement secondary sale order creation
                raise ValidationError("Only primary sale order creation is supported currently.")

            order_values = prepare_sale_order_values(request.env, payload)
            order = request.env["sale.order"].sudo().create(order_values)

            if parse_bool(payload.get("confirm")):
                order.action_confirm()

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Sale order created successfully.",
                "data": serialize_sale_order(order),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while creating the sale order.",
            )

    @http.route(f"{API_PREFIX}/sale-orders/<int:order_id>/update", type="json", auth="public", methods=["POST"])
    def update_sale_order(self, order_id, **payload):
        """Update a sale order with draft/sale restrictions."""
        try:
            if not order_id:
                raise ValidationError("'order_id' is required for updating.")

            order = request.env["sale.order"].sudo().browse(int(order_id)).exists()
            if not order:
                raise MissingError("No sale order found for the provided 'order_id'.")

            if order.state == "cancel":
                raise ValidationError("Cannot edit cancelled sale order.")
            if order.state == "done":
                raise ValidationError("Cannot edit done sale order.")

            # Check delivery/picking status
            was_confirmed = (order.state == "sale")
            if was_confirmed:
                # If confirmed, check if any pickings are done
                if any(p.state == "done" for p in order.picking_ids):
                    raise ValidationError("Cannot edit confirmed sale order with completed or partial delivery.")
                
                # Check distributor/customer change restriction
                if "distributor_id" in payload:
                    new_dist_id = _get_int(payload.get("distributor_id"), "distributor_id")
                    if new_dist_id != order.partner_id.id:
                        raise ValidationError("Cannot edit customer on confirmed sales order.")

            # Update lines if present in payload
            if "order_lines" in payload or "lines" in payload:
                order_lines = payload.get("order_lines") or payload.get("lines") or []
                update_sale_order_lines(request.env, order, order_lines, was_confirmed)

            # Update general fields
            vals = {}
            if "distributor_id" in payload and not was_confirmed:
                distributor = get_distributor(request.env, payload.get("distributor_id"))
                vals["partner_id"] = distributor.id
                vals["partner_shipping_id"] = distributor.id

            if "warehouse_id" in payload:
                vals["warehouse_id"] = _get_int(payload["warehouse_id"], "warehouse_id")

            if "expected_delivery_date" in payload:
                vals["commitment_date"] = payload["expected_delivery_date"]

            if "client_order_ref" in payload:
                vals["client_order_ref"] = payload["client_order_ref"]

            if vals:
                order.sudo().write(vals)

            # Reconfirm if originally draft but user requested confirm
            if not was_confirmed and parse_bool(payload.get("confirm")):
                order.action_confirm()

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Sale order updated successfully.",
                "data": serialize_sale_order(order),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while updating the sale order.",
            )

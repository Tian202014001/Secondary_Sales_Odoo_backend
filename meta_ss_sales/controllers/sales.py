# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    check_mobile_model_access,
    apply_mobile_rule_domain,
    mobile_rule_domain_allows_values,
)
from odoo.addons.meta_ss_sales.utils.sales import (
    build_sale_order_domain,
    get_employee,
    get_sales_pagination,
    parse_bool,
    prepare_sale_order_values,
    serialize_sale_order,
    get_distributor,
    update_sale_order_lines,
    _get_int,
)
from odoo.addons.meta_ss_sales.utils.sale_order_details import get_sale_order_for_employee


class MetaSSSalesController(http.Controller):

    @http.route(f"{API_PREFIX}/sale-orders", type="json", auth="user", methods=["POST"])
    def get_sale_orders(self, **payload):
        """Return sale orders filtered by sale_type and common dashboard filters."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            check_mobile_model_access(_mobile_user, "sale.order", "read")

            domain = build_sale_order_domain(payload)
            domain = apply_mobile_rule_domain(_mobile_user, "sale.order", "read", domain)

            limit, offset, page, page_size = get_sales_pagination(payload)

            SaleOrder = api_env["sale.order"].sudo()
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
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching sale orders.",
            )

    @http.route(f"{API_PREFIX}/sale-orders/create", type="json", auth="user", methods=["POST"])
    def create_sale_order(self, **payload):
        """Create a sale order using sale_type.

        Currently only sale_type='primary' is supported for creation.
        """
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            check_mobile_model_access(_mobile_user, "sale.order", "create")

            sale_type = (payload.get("sale_type") or "primary").strip()
            if sale_type != "primary":
                # TODO: Implement secondary sale order creation
                raise ValidationError("Only primary sale order creation is supported currently.")

            order_values = prepare_sale_order_values(api_env, payload)

            if not mobile_rule_domain_allows_values(api_env, _mobile_user, "sale.order", "create", order_values):
                raise AccessDenied("You do not have access to create this sale order based on your mobile rules.")

            order = api_env["sale.order"].create(order_values)

            if parse_bool(payload.get("confirm")):
                order.action_confirm()

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Sale order created successfully.",
                "data": serialize_sale_order(order),
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while creating the sale order.",
            )

    @http.route(f"{API_PREFIX}/sale-orders/<int:order_id>/update", type="json", auth="user", methods=["POST"])
    def update_sale_order(self, order_id, **payload):
        """Update a sale order with draft/sale restrictions."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            check_mobile_model_access(_mobile_user, "sale.order", "write")

            if not order_id:
                raise ValidationError("'order_id' is required for updating.")

            order = get_sale_order_for_employee(api_env, order_id, payload)

            rule_domain = apply_mobile_rule_domain(_mobile_user, "sale.order", "write", [("id", "=", order.id)])
            if not api_env["sale.order"].sudo().search_count(rule_domain):
                raise AccessDenied("You do not have access to update this sale order.")

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
                update_sale_order_lines(api_env, order, order_lines, was_confirmed)

            # Update general fields
            vals = {}
            if "distributor_id" in payload and not was_confirmed:
                employee = get_employee(api_env, payload.get("employee_id"))
                distributor = get_distributor(
                    api_env,
                    payload.get("distributor_id"),
                    employee=employee,
                )
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
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while updating the sale order.",
            )

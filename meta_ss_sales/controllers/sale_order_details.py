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
    check_mobile_model_access,
    apply_mobile_rule_domain,
    require_sale_type_access,
    require_ui_access,
)
from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey
from odoo.addons.meta_ss_sales.utils.sale_order_details import (
    get_sale_order_for_employee,
    perform_sale_order_action,
    serialize_sale_order_detail,
)


class MetaSSSaleOrderDetailsController(http.Controller):

    @http.route(f"{API_PREFIX}/sale-orders/<int:order_id>", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_sale_order_detail(self, order_id, **payload):
        """Return one sale order detail, optionally filtered by sale_type."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_ORDERS_DETAIL,
            AccessKey.SECONDARY_ORDERS_LIST,
        )
        # check_mobile_model_access(_mobile_user, "sale.order", "read")

        rule_domain = apply_mobile_rule_domain(_mobile_user, "sale.order", "read", [("id", "=", order_id)])
        if not api_env["sale.order"].sudo().search_count(rule_domain):
            raise AccessDenied("You do not have access to view this sale order.")

        order = get_sale_order_for_employee(api_env, order_id, payload)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Sale order fetched successfully.",
            "data": serialize_sale_order_detail(order),
        }

    @http.route(f"{API_PREFIX}/sale-orders/<int:order_id>/action", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def sale_order_action(self, order_id, **payload):
        """Run a sale order action such as confirm or cancel.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "employee_id": 7,
                    "sale_type": "primary",
                    "action": "cancel"
                },
                "id": 1
            }
        """
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        action = (payload.get("action") or "").strip().lower()
        if action == "confirm":
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_ORDERS_CONFIRM,
                AccessKey.SECONDARY_ORDERS_CONFIRM,
            )
        elif action == "cancel":
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_ORDERS_CANCEL,
                AccessKey.SECONDARY_ORDERS_CANCEL,
            )
        else:
            require_sale_type_access(
                _mobile_user,
                payload,
                AccessKey.PRIMARY_ORDERS_CREATE,
                AccessKey.SECONDARY_ORDERS_CREATE,
            )
        # check_mobile_model_access(_mobile_user, "sale.order", "write")

        rule_domain = apply_mobile_rule_domain(_mobile_user, "sale.order", "write", [("id", "=", order_id)])
        if not api_env["sale.order"].sudo().search_count(rule_domain):
            raise AccessDenied("You do not have access to perform actions on this sale order.")

        order = perform_sale_order_action(api_env, order_id, payload)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Sale order action completed successfully.",
            "data": serialize_sale_order_detail(order),
        }

    @http.route(f"{API_PREFIX}/sale-orders/<int:order_id>/print", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def print_sale_order(self, order_id, **payload):
        """Render the invoice PDF for a sale order and return it in base64 format.

        If no invoice exists for the sale order, falls back to the sale order PDF.
        """
        import base64
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
        require_sale_type_access(
            _mobile_user,
            payload,
            AccessKey.PRIMARY_ORDERS_DETAIL,
            AccessKey.SECONDARY_ORDERS_LIST,
        )
        # check_mobile_model_access(_mobile_user, "sale.order", "read")

        rule_domain = apply_mobile_rule_domain(_mobile_user, "sale.order", "read", [("id", "=", order_id)])
        if not api_env["sale.order"].sudo().search_count(rule_domain):
            raise AccessDenied("You do not have access to print this sale order.")

        order = get_sale_order_for_employee(api_env, order_id, payload)

        # Prefer the invoice PDF (with payment info)
        invoices = order.invoice_ids.filtered(lambda inv: inv.state != "cancel")
        if invoices:
            invoice = invoices.sorted("id", reverse=True)[:1]
            pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'account.account_invoices', [invoice.id]
            )[0]
            filename = f"{invoice.name or order.name}_invoice.pdf"
        else:
            # Fallback to sale order PDF
            pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf(
                'sale.action_report_saleorder', [order.id]
            )[0]
            filename = f"{order.name}.pdf"

        pdf_base64 = base64.b64encode(pdf).decode('utf-8')
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "PDF generated successfully.",
            "data": {
                "filename": filename,
                "file_content": pdf_base64,
            },
        }


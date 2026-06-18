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
from odoo.addons.meta_ss_sales.utils.sale_order_details import (
    get_sale_order_for_employee,
    perform_sale_order_action,
    serialize_sale_order_detail,
)


class MetaSSSaleOrderDetailsController(http.Controller):

    @http.route(f"{API_PREFIX}/sale-orders/<int:order_id>", type="json", auth="user", methods=["POST"])
    def get_sale_order_detail(self, order_id, **payload):
        """Return one sale order detail, optionally filtered by sale_type."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            order = get_sale_order_for_employee(api_env, order_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Sale order fetched successfully.",
                "data": serialize_sale_order_detail(order),
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching the sale order.",
            )

    @http.route(f"{API_PREFIX}/sale-orders/<int:order_id>/action", type="json", auth="user", methods=["POST"])
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
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            order = perform_sale_order_action(api_env, order_id, payload)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Sale order action completed successfully.",
                "data": serialize_sale_order_detail(order),
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while running the sale order action.",
            )

    @http.route(f"{API_PREFIX}/sale-orders/<int:order_id>/print", type="json", auth="user", methods=["POST"])
    def print_sale_order(self, order_id, **payload):
        """Render the invoice PDF for a sale order and return it in base64 format.

        If no invoice exists for the sale order, falls back to the sale order PDF.
        """
        try:
            import base64
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
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
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while printing the sale order.",
            )

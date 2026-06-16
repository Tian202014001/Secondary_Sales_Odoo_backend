# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    check_api_permission,
    error_response,
)
from odoo.addons.meta_ss_contact.utils.contacts import (
    build_contact_domain,
    ensure_distributor_locations,
    get_contact_pagination,
    normalize_customer_type,
    prepare_contact_values,
    prepare_contact_update_values,
    serialize_contacts,
)


class MetaSSContactController(http.Controller):

    @http.route(f"{API_PREFIX}/contacts", type="json", auth="public", methods=["POST"])
    def get_contacts(self, **payload):
        """List/search contacts using customer_type and optional filters.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "customer_type": "outlet",
                    "employee_id": 7,
                    "route_id": 12,
                    "search": "Hasan",
                    "page": 1,
                    "page_size": 20
                },
                "id": 1
            }
        """
        try:
            # mobile_user = check_api_permission()
            customer_type = normalize_customer_type(payload, required=False)

            allowed_types = ["distributor", "outlet"]
            if customer_type:
                if customer_type not in allowed_types:
                    raise AccessDenied(f"You do not have permission to view {customer_type} contacts.")

            domain = build_contact_domain(request.env, payload, customer_type)
            limit, offset, page, page_size = get_contact_pagination(payload)
            Partner = request.env["res.partner"].sudo()
            contacts = Partner.search(domain, limit=limit, offset=offset, order="name")
            total = Partner.search_count(domain)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Contacts fetched successfully.",
                "data": serialize_contacts(contacts),
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": total,
                },
            }
        except AccessDenied as exc:
            return error_response("access_denied", str(exc))
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching contacts.",
            )

    @http.route(f"{API_PREFIX}/contacts/create", type="json", auth="public", methods=["POST"])
    def create_contact(self, **payload):
        """Create a distributor or outlet contact using customer_type."""
        try:
            customer_type = normalize_customer_type(payload)
            # check_api_permission(f"{customer_type}_create")
            contact = request.env["res.partner"].sudo().create(
                prepare_contact_values(payload, customer_type)
            )
            if customer_type == "distributor":
                ensure_distributor_locations(request.env, contact)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Contact created successfully.",
                "data": serialize_contacts(contact)[0],
            }
        except AccessDenied as exc:
            return error_response("access_denied", str(exc))
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception as exc:
            request.env.cr.rollback()
            logging.getLogger(__name__).exception("create_contact failed")
            return error_response(
                "server_error",
                "An unexpected error occurred while creating contact. Please contact support.",
            )

    @http.route(f"{API_PREFIX}/contacts/<int:contact_id>", type="json", auth="public", methods=["POST"])
    def get_contact(self, contact_id, **payload):
        """Return one contact by id, optionally validating customer_type."""
        try:
            # mobile_user = check_api_permission()
            contact = request.env["res.partner"].sudo().browse(contact_id).exists()
            if not contact:
                raise ValidationError("No contact was found for the provided id.")

            customer_type = normalize_customer_type(payload, required=False)
            if customer_type and contact.customer_type != customer_type:
                raise ValidationError("The requested contact does not match 'customer_type'.")

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Contact fetched successfully.",
                "data": serialize_contacts(contact)[0],
            }
        except AccessDenied as exc:
            return error_response("access_denied", str(exc))
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching contact.",
            )

    @http.route(f"{API_PREFIX}/contacts/<int:contact_id>/update", type="json", auth="public", methods=["POST"])
    def update_contact(self, contact_id, **payload):
        """Update an existing distributor or outlet contact using customer_type."""
        try:
            # check_api_permission()
            customer_type = normalize_customer_type(payload)
            contact = request.env["res.partner"].sudo().browse(contact_id).exists()
            if not contact:
                raise ValidationError("No contact was found for the provided id.")

            vals = prepare_contact_update_values(payload, customer_type)
            if vals:
                contact.write(vals)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Contact updated successfully.",
                "data": serialize_contacts(contact)[0],
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while updating contact.",
            )

    @http.route(f"{API_PREFIX}/contacts/<int:contact_id>/visits", type="json", auth="public", methods=["POST"])
    def get_contact_visit_history(self, contact_id, **payload):
        """Fetch past check-in/out logs and sales orders for a specific contact/outlet."""
        try:
            contact = request.env["res.partner"].sudo().browse(contact_id).exists()
            if not contact:
                return error_response("not_found", "No contact was found for the provided id.")

            # Get past route visit lines for this outlet
            visit_lines = request.env["sale.route.visit.line"].sudo().search([
                ("outlet_id", "=", contact.id),
                ("state", "in", ["checked_in", "checked_out", "skipped"]),
            ], order="check_in_time desc", limit=20)

            # Get past sales orders for this outlet
            orders = request.env["sale.order"].sudo().search([
                ("partner_id", "=", contact.id),
                ("state", "in", ["sale", "done"]),
            ], order="date_order desc", limit=20)

            visit_logs_data = []
            for line in visit_lines:
                visit_logs_data.append({
                    "id": line.id,
                    "visit_id": line.visit_id.id,
                    "visit_date": str(line.visit_id.visit_date),
                    "state": line.state,
                    "check_in_time": str(line.check_in_time) if line.check_in_time else None,
                    "check_out_time": str(line.check_out_time) if line.check_out_time else None,
                    "note": line.note or None,
                })

            past_orders_data = []
            for order in orders:
                past_orders_data.append({
                    "id": order.id,
                    "name": order.name,
                    "date_order": str(order.date_order),
                    "amount_total": order.amount_total,
                    "state": order.state,
                })

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Visit history fetched successfully.",
                "data": {
                    "contact_id": contact.id,
                    "contact_name": contact.name,
                    "visit_logs": visit_logs_data,
                    "past_orders": past_orders_data,
                }
            }
        except Exception as exc:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching visit history: " + str(exc),
            )

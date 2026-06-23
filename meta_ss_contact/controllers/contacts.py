# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    apply_mobile_rule_domain,
    check_mobile_model_access,
    error_response,
    get_mobile_api_context,
    mobile_rule_domain_allows_values,
)
from odoo.addons.meta_ss_contact.utils.contacts import (
    build_contact_order_history_domain,
    build_contact_visit_history_domain,
    build_contact_domain,
    ensure_distributor_locations,
    get_contact_pagination,
    get_contact_for_payload,
    normalize_customer_type,
    prepare_contact_values,
    prepare_contact_update_values,
    serialize_contacts,
)


class MetaSSContactController(http.Controller):

    @http.route(f"{API_PREFIX}/contacts", type="json", auth="user", methods=["POST"])
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
            mobile_user, api_env, payload = get_mobile_api_context(payload)
            check_mobile_model_access(mobile_user, "res.partner", "read")
            customer_type = normalize_customer_type(payload, required=False)

            allowed_types = ["distributor", "outlet"]
            if customer_type:
                if customer_type not in allowed_types:
                    raise AccessDenied(f"You do not have permission to view {customer_type} contacts.")
                if not mobile_rule_domain_allows_values(
                    api_env,
                    mobile_user,
                    "res.partner",
                    "read",
                    {"customer_type": customer_type, "active": True},
                ):
                    raise AccessDenied(f"You do not have permission to view {customer_type} contacts.")

            domain = build_contact_domain(api_env, payload, customer_type)
            domain = apply_mobile_rule_domain(mobile_user, "res.partner", "read", domain)
            limit, offset, page, page_size = get_contact_pagination(payload)
            
            order_by = "name"
            if payload.get("sort") == "recent":
                order_by = "create_date desc, id desc"
                
            Partner = api_env["res.partner"].sudo()
            contacts = Partner.search(domain, limit=limit, offset=offset, order=order_by)
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
            logging.getLogger(__name__).exception("get_contacts failed")
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching contacts.",
            )

    @http.route(f"{API_PREFIX}/contacts/create", type="json", auth="user", methods=["POST"])
    def create_contact(self, **payload):
        """Create a distributor or outlet contact using customer_type."""
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload)
            check_mobile_model_access(mobile_user, "res.partner", "create")
            customer_type = normalize_customer_type(payload)
            if not mobile_rule_domain_allows_values(
                api_env,
                mobile_user,
                "res.partner",
                "create",
                {"customer_type": customer_type, "active": True},
            ):
                raise AccessDenied("You do not have access to create this contact type.")
            # check_api_permission(f"{customer_type}_create")
            contact = api_env["res.partner"].sudo().create(
                prepare_contact_values(payload, customer_type)
            )
            if customer_type == "distributor":
                ensure_distributor_locations(api_env, contact)

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

    @http.route(f"{API_PREFIX}/contacts/<int:contact_id>", type="json", auth="user", methods=["POST"])
    def get_contact(self, contact_id, **payload):
        """Return one contact by id, optionally validating customer_type."""
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload)
            check_mobile_model_access(mobile_user, "res.partner", "read")
            customer_type = normalize_customer_type(payload, required=False)
            contact = get_contact_for_payload(api_env, contact_id, payload, customer_type)
            rule_domain = apply_mobile_rule_domain(
                mobile_user,
                "res.partner",
                "read",
                [("id", "=", contact.id)],
            )
            if not api_env["res.partner"].sudo().search_count(rule_domain):
                raise AccessDenied("You do not have access to this contact.")

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
            logging.getLogger(__name__).exception("get_contact failed")
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching contact.",
            )

    @http.route(f"{API_PREFIX}/contacts/<int:contact_id>/update", type="json", auth="user", methods=["POST"])
    def update_contact(self, contact_id, **payload):
        """Update an existing distributor or outlet contact using customer_type."""
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload)
            check_mobile_model_access(mobile_user, "res.partner", "write")
            customer_type = normalize_customer_type(payload)
            contact = get_contact_for_payload(api_env, contact_id, payload, customer_type)
            rule_domain = apply_mobile_rule_domain(
                mobile_user,
                "res.partner",
                "write",
                [("id", "=", contact.id)],
            )
            if not api_env["res.partner"].sudo().search_count(rule_domain):
                raise AccessDenied("You do not have access to update this contact.")

            vals = prepare_contact_update_values(payload, customer_type)
            if "customer_type" in vals and vals["customer_type"] != contact.customer_type:
                raise ValidationError("Changing contact type is not allowed from this API.")
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
            logging.getLogger(__name__).exception("update_contact failed")
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while updating contact.",
            )

    @http.route(f"{API_PREFIX}/contacts/<int:contact_id>/visits", type="json", auth="user", methods=["POST"])
    def get_contact_visit_history(self, contact_id, **payload):
        """Fetch past check-in/out logs and sales orders for a specific contact/outlet."""
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload)
            check_mobile_model_access(mobile_user, "res.partner", "read")
            contact = get_contact_for_payload(api_env, contact_id, payload, payload.get("customer_type"))
            rule_domain = apply_mobile_rule_domain(
                mobile_user,
                "res.partner",
                "read",
                [("id", "=", contact.id)],
            )
            if not api_env["res.partner"].sudo().search_count(rule_domain):
                raise AccessDenied("You do not have access to this contact.")

            orders = api_env["sale.order"].search(
                build_contact_order_history_domain(contact, payload),
                order="date_order desc",
                limit=20,
            )
            visits = api_env["outlet.visit"].search(
                build_contact_visit_history_domain(contact, payload),
                order="check_in_time desc",
                limit=20,
            )

            visit_logs_data = []
            for visit in visits:
                visit_logs_data.append({
                    "id": visit.id,
                    "employee_id": visit.employee_id.id,
                    "employee_name": visit.employee_id.name,
                    "check_in_time": str(visit.check_in_time) if visit.check_in_time else None,
                    "check_out_time": str(visit.check_out_time) if visit.check_out_time else None,
                    "visit_type": visit.visit_type,
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
        except AccessDenied as exc:
            return error_response("access_denied", str(exc))
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception as exc:
            logging.getLogger(__name__).exception("get_contact_visit_history failed")
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching visit history: " + str(exc),
            )

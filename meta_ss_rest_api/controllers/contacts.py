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
from odoo.addons.meta_ss_rest_api.utils.contacts import (
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

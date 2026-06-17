# -*- coding: utf-8 -*-

import logging
from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
)
from odoo.addons.meta_ss_transfer.utils.virtual_locations import (
    build_virtual_location_domain,
    create_van_scrap_sibling,
    get_virtual_location_pagination,
    prepare_virtual_location_vals,
    serialize_virtual_location,
)


class MetaSSVirtualLocationController(http.Controller):

    @http.route(f"{API_PREFIX}/virtual-locations", type="json", auth="user", methods=["POST"])
    def get_virtual_locations(self, **payload):
        """List van loading virtual locations.

        Request:
            {
                "employee_id": 7,
                "location_type": "van_loading",
                "search": "Anita",
                "page": 1,
                "page_size": 20
            }
        """
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            domain = build_virtual_location_domain(api_env, payload)
            limit, offset, page, page_size = get_virtual_location_pagination(payload)
            Location = api_env["stock.location"]
            locations = Location.search(domain, limit=limit, offset=offset, order="name")
            total = Location.search_count(domain)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Virtual locations fetched successfully.",
                "data": [serialize_virtual_location(loc) for loc in locations],
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
                "An unexpected error occurred while fetching virtual locations.",
            )

    @http.route(f"{API_PREFIX}/virtual-locations/create", type="json", auth="user", methods=["POST"])
    def create_virtual_location(self, **payload):
        """Create a van loading location and assign employee/distributor.

        Request:
            {
                "employee_id": 7,
                "name": "Anita Oliver - Distributor A Van Loading",
                "location_type": "van_loading",
                "assigned_employee_id": 7,
                "assigned_distributor_id": 3
            }
        """
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            vals = prepare_virtual_location_vals(api_env, payload)
            location = api_env["stock.location"].create(vals)
            # Recompute full path so display_name includes parent chain
            location._compute_complete_name()
            location.flush_recordset(["complete_name"])

            # Derive distributor name and van name from the stock location name
            # Name format: "<distributor> - <van> - Stock"
            distributor = api_env["res.partner"].browse(
                vals["ss_distributor_id"]
            )
            van_name = (payload.get("name") or "").strip()
            scrap_loc = create_van_scrap_sibling(
                api_env, location, distributor.name, van_name
            )

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Virtual location created successfully.",
                "data": serialize_virtual_location(location),
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception as exc:
            request.env.cr.rollback()
            logging.getLogger(__name__).exception("create_virtual_location failed")
            return error_response(
                "server_error",
                "An unexpected error occurred while creating virtual location: %s" % str(exc),
            )

    @http.route(f"{API_PREFIX}/virtual-locations/<int:location_id>", type="json", auth="user", methods=["POST"])
    def get_virtual_location_detail(self, location_id, **payload):
        """Virtual location detail."""
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=True)
            location = api_env["stock.location"].browse(location_id).exists()
            if not location or location.ss_location_type != "van_loading":
                return error_response("not_found", "Virtual location not found.")

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Virtual location fetched successfully.",
                "data": serialize_virtual_location(location),
            }
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching virtual location detail.",
            )

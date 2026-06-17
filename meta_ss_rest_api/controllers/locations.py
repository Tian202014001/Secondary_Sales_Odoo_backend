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
from odoo.addons.meta_ss_rest_api.utils.locations import (
    build_location_domain,
    get_location_pagination,
    serialize_location,
)


class MetaSSLocationController(http.Controller):

    @http.route(f"{API_PREFIX}/locations", type="json", auth="user", methods=["POST"])
    def get_locations(self, **payload):
        """List and search stock locations.

        Request:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "usage": "internal",
                    "ss_location_type": "van_loading",
                    "employee_id": 7,
                    "search": "Van",
                    "page": 1,
                    "page_size": 20
                },
                "id": 1
            }

        Response:
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "success": true,
                    "api_version": "v1",
                    "message": "Locations fetched successfully.",
                    "data": [
                        {
                            "id": 48,
                            "name": "Van Loading 1",
                            "complete_name": "Physical Locations/WH/Stock/Van Loading 1",
                            "display_name": "WH/Stock/Van Loading 1",
                            "usage": "internal",
                            "active": true,
                            "ss_location_type": "van_loading",
                            "employee": {"id": 7, "name": "Sales Officer 1"},
                            "distributor": {"id": 3, "name": "Distributor A"}
                        }
                    ],
                    "pagination": {
                        "page": 1,
                        "page_size": 20,
                        "total": 1
                    }
                }
            }
        """
        try:
            _mobile_user, api_env, payload = get_mobile_api_context(payload)
            domain = build_location_domain(api_env, payload)
            limit, offset, page, page_size = get_location_pagination(payload)
            
            Location = api_env["stock.location"]
            locations = Location.search(domain, limit=limit, offset=offset, order="complete_name, id")
            total = Location.search_count(domain)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Locations fetched successfully.",
                "data": [serialize_location(loc) for loc in locations],
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
                "An unexpected error occurred while fetching locations.",
            )

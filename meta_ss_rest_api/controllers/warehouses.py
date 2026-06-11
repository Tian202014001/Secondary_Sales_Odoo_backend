# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request

from odoo.addons.meta_ss_rest_api.utils.common import API_PREFIX, API_VERSION, error_response
from odoo.addons.meta_ss_rest_api.utils.warehouses import (
    build_available_lot_domain,
    build_warehouse_domain,
    get_warehouse_pagination,
    serialize_available_lots,
    serialize_warehouse,
)


class MetaSSWarehouseController(http.Controller):

    @http.route(f"{API_PREFIX}/warehouses", type="json", auth="public", methods=["POST"])
    def get_warehouses(self, **payload):
        """Return warehouses for delivery source selection.

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "search": "WH",
                    "page": 1,
                    "page_size": 20
                },
                "id": 1
            }

        Response body example:
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "success": true,
                    "api_version": "v1",
                    "message": "Warehouses fetched successfully.",
                    "data": [
                        {
                            "id": 1,
                            "name": "My Company Warehouse",
                            "code": "WH",
                            "stock_location": {
                                "id": 8,
                                "name": "WH/Stock",
                                "usage": "internal"
                            }
                        }
                    ],
                    "pagination": {"page": 1, "page_size": 20, "total": 1}
                }
            }
        """
        try:
            domain = build_warehouse_domain(request.env, payload)
            limit, offset, page, page_size = get_warehouse_pagination(payload)
            Warehouse = request.env["stock.warehouse"].sudo()
            warehouses = Warehouse.search(domain, limit=limit, offset=offset, order="name")
            total = Warehouse.search_count(domain)

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Warehouses fetched successfully.",
                "data": [serialize_warehouse(warehouse) for warehouse in warehouses],
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
                "An unexpected error occurred while fetching warehouses.",
            )

    @http.route(
        f"{API_PREFIX}/products/<int:product_id>/available-lots",
        type="json",
        auth="public",
        methods=["POST"],
    )
    def get_product_available_lots(self, product_id, **payload):
        """Return available lots for a product under a warehouse/location.

        Request URL example:
            POST /api/v1/products/25/available-lots

        Request body example:
            {
                "jsonrpc": "2.0",
                "method": "call",
                "params": {
                    "warehouse_id": 1
                },
                "id": 1
            }

        Alternative request params:
            {
                "location_id": 8
            }

        Response body example:
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": {
                    "success": true,
                    "api_version": "v1",
                    "message": "Available lots fetched successfully.",
                    "product": {
                        "id": 25,
                        "name": "Eggs",
                        "tracking": "lot"
                    },
                    "location": {
                        "id": 8,
                        "name": "WH/Stock"
                    },
                    "data": [
                        {
                            "lot_id": 7,
                            "lot_name": "LOT-001",
                            "product_id": 25,
                            "available_qty": 10.0,
                            "quantity": 10.0,
                            "reserved_quantity": 0.0,
                            "uom": {"id": 1, "name": "Dzn"},
                            "location": {"id": 8, "name": "WH/Stock"}
                        }
                    ]
                }
            }
        """
        try:
            payload = dict(payload)
            payload["product_id"] = product_id
            product, location, domain = build_available_lot_domain(request.env, payload)
            Quant = request.env["stock.quant"].sudo()
            quants = Quant.search(domain, order="location_id, lot_id")

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Available lots fetched successfully.",
                "product": {
                    "id": product.id,
                    "name": product.display_name,
                    "tracking": product.tracking,
                },
                "location": {
                    "id": location.id,
                    "name": location.display_name,
                },
                "data": serialize_available_lots(quants),
            }
        except (AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching available lots.",
            )

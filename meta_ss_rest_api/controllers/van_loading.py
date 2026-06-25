# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessDenied, AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from datetime import date

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
)

class MetaSSVanLoadingController(http.Controller):

    @http.route(f"{API_PREFIX}/van_loading/targets", type="json", auth="user", methods=["POST"])
    def get_van_loading_targets(self, **payload):
        """Fetch monthly target products for van loading with current distributor stock."""
        try:
            mobile_user, api_env, trusted_payload = get_mobile_api_context(payload, require_employee=True)
            employee_id = trusted_payload.get("employee_id")
            
            if not employee_id:
                raise ValidationError("Employee ID is required.")
                
            employee = api_env["hr.employee"].browse(employee_id)
            if not employee.exists():
                raise ValidationError("Employee not found.")
                
            if not employee.distributor_contact_ids:
                raise ValidationError("Employee is not assigned to any distributor.")
                
            distributor = employee.distributor_contact_ids[0]
            source_location = distributor.property_stock_customer
            if not source_location:
                raise ValidationError("Distributor does not have a customer stock location.")
                
            van_op_type = payload.get("van_operation_type", "load")
            
            # Resolve locations based on load / unload
            van_location = api_env["stock.location"]
            van_scrap_location = api_env["stock.location"]
            if van_op_type == "unload":
                destination_location_id = payload.get("destination_location_id")
                if destination_location_id:
                    van_location = api_env["stock.location"].sudo().browse(int(destination_location_id))
                else:
                    van_location = api_env["stock.location"].sudo().search([
                        ("ss_location_type", "=", "van_loading"),
                        ("scrap_location", "=", False),
                        ("ss_employee_id", "=", employee.id),
                        ("active", "=", True),
                    ], limit=1)
                if not van_location.exists():
                    raise ValidationError("Van location not found.")
                
                van_scrap_location = api_env["stock.location"].sudo().search([
                    ("ss_location_type", "=", "van_loading"),
                    ("scrap_location", "=", True),
                    ("ss_employee_id", "=", van_location.ss_employee_id.id),
                    ("ss_distributor_id", "=", van_location.ss_distributor_id.id),
                    ("active", "=", True),
                ], limit=1)
                
            today = date.today()
            month_str = f"{today.month:02d}"
            year_str = str(today.year)
            
            target_lines = api_env["sale.target.line"].search([
                ("employee_id", "=", employee.id),
                ("target_id.month", "=", month_str),
                ("target_id.year", "=", year_str),
            ])
            
            products = target_lines.mapped("product_id")
            stock_lookup = {}
            scrap_lookup = {}
            
            for product in products:
                if van_op_type == "unload":
                    # Fetch fresh stock in van
                    fresh_domain = [
                        ("product_id", "=", product.id),
                        ("location_id", "child_of", van_location.id),
                        ("available_quantity", ">", 0),
                    ]
                    quants = api_env["stock.quant"].sudo().search(fresh_domain)
                    stock_lookup[product.id] = sum(quants.mapped("available_quantity"))
                    
                    # Fetch scrap stock in van
                    if van_scrap_location:
                        scrap_domain = [
                            ("product_id", "=", product.id),
                            ("location_id", "child_of", van_scrap_location.id),
                            ("available_quantity", ">", 0),
                        ]
                        s_quants = api_env["stock.quant"].sudo().search(scrap_domain)
                        scrap_lookup[product.id] = sum(s_quants.mapped("available_quantity"))
                    else:
                        scrap_lookup[product.id] = 0.0
                else:
                    # Load: Fetch stock in distributor location, excluding van_loading
                    domain = [
                        ("product_id", "=", product.id),
                        ("location_id", "child_of", source_location.id),
                        ("available_quantity", ">", 0),
                    ]
                    if source_location.ss_location_type != "van_loading":
                        domain.append(("location_id.ss_location_type", "!=", "van_loading"))
                    quants = api_env["stock.quant"].sudo().search(domain)
                    stock_lookup[product.id] = sum(quants.mapped("available_quantity"))
                    scrap_lookup[product.id] = 0.0
            
            data = []
            for t_line in target_lines:
                product = t_line.product_id
                available_stock = stock_lookup.get(product.id, 0.0)
                if available_stock < 0:
                    available_stock = 0.0
                    
                scrap_stock = scrap_lookup.get(product.id, 0.0)
                if scrap_stock < 0:
                    scrap_stock = 0.0
                    
                data.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "sku": product.default_code or "",
                    "tracking": product.tracking,
                    "uom_id": product.uom_id.id,
                    "uom_name": product.uom_id.name,
                    "daily_target_qty": t_line.daily_target_qty,
                    "available_stock": available_stock,
                    "scrap_stock": scrap_stock,
                })
                
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Van loading targets fetched successfully.",
                "data": data,
            }
            
        except (AccessDenied, AccessError, MissingError, UserError, ValidationError) as exc:
            return error_response("validation_error", str(exc))
        except Exception:
            request.env.cr.rollback()
            return error_response(
                "server_error",
                "An unexpected error occurred while fetching van loading targets.",
            )

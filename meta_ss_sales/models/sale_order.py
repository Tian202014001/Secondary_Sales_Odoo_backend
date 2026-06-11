# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sale_type = fields.Selection(
        selection=[
            ('primary', 'Primary'),
            ('secondary', 'Secondary'),
        ],
        string="Sale Type",
        default="primary",
    )
    
    so_employee_id = fields.Many2one(
        'hr.employee',
        string="Sales Employee",
        help="Employee responsible for this sales order"
    )
    
    route_id = fields.Many2one(
        'sale.route',
        string="Route",
        domain="[('active', '=', True)]",
        help="Route associated with this sales order"
    )
    
    route_visit_id = fields.Many2one(
        'sale.route.visit',
        string="Route Visit",
        help="Route visit/session where this sales order was created"
    )
    
    route_visit_line_id = fields.Many2one(
        'sale.route.visit.line',
        string="Outlet Visit",
        help="Outlet visit where this sales order was created"
    )

    @api.onchange("so_employee_id")
    def _onchange_so_employee_id(self):
        if (
            self.route_id
            and self.route_id.ss_employee_ids
            and self.so_employee_id not in self.route_id.ss_employee_ids
        ):
            self.route_id = False
        if self.route_visit_id and self.route_visit_id.employee_id != self.so_employee_id:
            self.route_visit_id = False
            self.route_visit_line_id = False

    @api.onchange("route_id")
    def _onchange_route_id(self):
        if self.route_id and len(self.route_id.ss_employee_ids) == 1:
            self.so_employee_id = self.route_id.ss_employee_ids.id
        if self.route_visit_id and self.route_visit_id.route_id != self.route_id:
            self.route_visit_id = False
            self.route_visit_line_id = False

    @api.onchange("route_visit_id")
    def _onchange_route_visit_id(self):
        if not self.route_visit_id:
            self.route_visit_line_id = False
            return
        self.so_employee_id = self.route_visit_id.employee_id
        self.route_id = self.route_visit_id.route_id
        if self.route_visit_line_id and self.route_visit_line_id.visit_id != self.route_visit_id:
            self.route_visit_line_id = False

    @api.onchange("route_visit_line_id")
    def _onchange_route_visit_line_id(self):
        if not self.route_visit_line_id:
            return
        self.route_visit_id = self.route_visit_line_id.visit_id
        self.so_employee_id = self.route_visit_id.employee_id
        self.route_id = self.route_visit_id.route_id
        self.partner_id = self.route_visit_line_id.outlet_id

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_route_visit_defaults(vals)
        orders = super().create(vals_list)
        orders._mark_route_visit_lines_visited()
        return orders

    def write(self, vals):
        vals = dict(vals)
        self._apply_route_visit_defaults(vals)
        result = super().write(vals)
        if "route_visit_line_id" in vals:
            self._mark_route_visit_lines_visited()
        return result

    def _apply_route_visit_defaults(self, vals):
        if vals.get("route_visit_line_id"):
            visit_line = self.env["sale.route.visit.line"].browse(vals["route_visit_line_id"])
            visit = visit_line.visit_id
            vals["route_visit_id"] = visit.id
            vals["so_employee_id"] = visit.employee_id.id
            vals["route_id"] = visit.route_id.id
            vals["partner_id"] = visit_line.outlet_id.id
        elif vals.get("route_visit_id"):
            visit = self.env["sale.route.visit"].browse(vals["route_visit_id"])
            vals["so_employee_id"] = visit.employee_id.id
            vals["route_id"] = visit.route_id.id

    def _mark_route_visit_lines_visited(self):
        visit_lines = self.mapped("route_visit_line_id").filtered(lambda line: line.state == "pending")
        if visit_lines:
            visit_lines.write({"state": "visited"})


# class SaleOrderLine(models.Model):
#     _inherit = "sale.order.line"

#     def _prepare_procurement_values(self, group_id=False):
#         values = super()._prepare_procurement_values(group_id=group_id)
#         self.ensure_one()

#         default_location = self.order_id.partner_shipping_id.default_location_id
#         if default_location:
#             values.update({
#                 "location_dest_id": default_location.id,
#                 "location_final_id": default_location.id,
#             })

#         return values


# class StockRule(models.Model):
#     _inherit = "stock.rule"

#     def _get_custom_move_fields(self):
#         fields = super()._get_custom_move_fields()
#         fields += ["location_dest_id", "location_final_id"]
#         return fields

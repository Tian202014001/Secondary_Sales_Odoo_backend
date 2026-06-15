# -*- coding: utf-8 -*-

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sale_type = fields.Selection(
        selection=[
            ('primary', 'Primary'),
            ('secondary', 'Secondary'),
        ],
        string="Sale Type"
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

    def _action_confirm(self):
        result = super()._action_confirm()
        for order in self:
            if order.sale_type == 'secondary':
                damaged_lines = order.order_line.filtered(lambda l: l.damaged_qty > 0)
                if damaged_lines and order.so_employee_id:
                    virtual_scrap = self.env['stock.location'].search([
                        ('ss_employee_id', '=', order.so_employee_id.id),
                        ('scrap_location', '=', True)
                    ], limit=1)
                    
                    customer_loc = order.partner_shipping_id.property_stock_customer or self.env.ref('stock.stock_location_customers', raise_if_not_found=False)
                    
                    if virtual_scrap and customer_loc:
                        picking_type_in = self.env['stock.picking.type'].search([
                            ('code', '=', 'incoming'),
                            ('company_id', '=', order.company_id.id)
                        ], limit=1)
                        
                        if picking_type_in:
                            receipt_picking = self.env['stock.picking'].create({
                                'partner_id': order.partner_shipping_id.id or order.partner_id.id,
                                'picking_type_id': picking_type_in.id,
                                'location_id': customer_loc.id,
                                'location_dest_id': virtual_scrap.id,
                                'origin': f"{order.name} - Damaged Return",
                                'company_id': order.company_id.id,
                            })
                            
                            for line in damaged_lines:
                                self.env['stock.move'].create({
                                    'name': line.name or line.product_id.name,
                                    'product_id': line.product_id.id,
                                    'product_uom_qty': line.damaged_qty,
                                    'product_uom': line.product_uom.id,
                                    'picking_id': receipt_picking.id,
                                    'location_id': customer_loc.id,
                                    'location_dest_id': virtual_scrap.id,
                                    'sale_line_id': line.id,
                                    'company_id': order.company_id.id,
                                })
                            
                            receipt_picking.action_confirm()
                            
                try:
                    invoices = order.with_context(raise_if_nothing_to_invoice=False)._create_invoices(final=True)
                    for invoice in invoices:
                        invoice.action_post()
                except Exception as e:
                    pass
                            
        return result

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    damaged_qty = fields.Float(string="Damaged Quantity", default=0.0)

    def _get_qty_procurement(self, previous_product_uom_qty=False):
        qty = super()._get_qty_procurement(previous_product_uom_qty=previous_product_uom_qty)
        if self.order_id.sale_type == 'secondary':
            # Subtract damaged_qty from already procured quantity so the system generates MORE demand
            qty -= self.damaged_qty
        return qty

    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id=group_id)
        if self.order_id.sale_type == 'secondary' and self.order_id.so_employee_id:
            virtual_stock = self.env['stock.location'].search([
                ('ss_employee_id', '=', self.order_id.so_employee_id.id),
                ('scrap_location', '=', False),
            ], limit=1)
            if virtual_stock:
                values.update({
                    "location_id": virtual_stock.id,
                })
        return values

class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_custom_move_fields(self):
        fields = super()._get_custom_move_fields()
        fields += ["location_id"]
        return fields

from odoo import Command, _, api, fields, models
import calendar
from datetime import date, timedelta
import math

class SaleTarget(models.Model):
    _name = "sale.target"
    _description = "Sale Target"

    name = fields.Char(string='Name', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    distributor_id = fields.Many2one('res.partner', string='Distributor', required=True, domain="[('customer_type', '=', 'distributor')]")
    target_line_ids = fields.One2many('sale.target.line', 'target_id', string='Target Lines')
    
    month = fields.Selection([
        ('01', 'January'), ('02', 'February'), ('03', 'March'), ('04', 'April'),
        ('05', 'May'), ('06', 'June'), ('07', 'July'), ('08', 'August'),
        ('09', 'September'), ('10', 'October'), ('11', 'November'), ('12', 'December')
    ], string='Month', required=True)
    
    year = fields.Char(string='Year', required=True, default=lambda self: str(date.today().year))
    
    date_from = fields.Date(string='Date From', required=True)
    date_to = fields.Date(string='Date To', required=True)

    @api.onchange('month', 'year')
    def _onchange_month_year(self):
        if self.month and self.year and self.year.isdigit():
            try:
                year = int(self.year)
                month = int(self.month)
                _, last_day = calendar.monthrange(year, month)
                self.date_from = date(year, month, 1)
                self.date_to = date(year, month, last_day)
            except Exception:
                pass

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                seq = self.env['ir.sequence'].next_by_code('sale.target') or '000'
                month = vals.get('month', '00')
                year = vals.get('year', '0000')
                vals['name'] = f"TARGET/{year}/{month}/{seq}"
        return super().create(vals_list)


class SaleTargetLine(models.Model):
    _name = "sale.target.line"
    _description = "Sale Target Line"

    target_id = fields.Many2one('sale.target', string='Target Reference', required=True, ondelete='cascade')
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, domain="[('distributor_contact_ids', 'in', target_id.distributor_id)]")
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom = fields.Many2one('uom.uom', string='UOM', related='product_id.uom_id', readonly=True)
    target_qty = fields.Float(string='Target Quantity', default=0.0)
    daily_target_qty = fields.Float(string='Daily Target Qty', compute='_compute_daily_target_qty')
    achieved_target_qty = fields.Float(string='Achieved Target Qty', compute='_compute_achieved_target_qty')

    def _compute_achieved_target_qty(self):
        for line in self:
            qty = 0.0
            if line.employee_id and line.product_id and line.target_id.date_from and line.target_id.date_to:
                domain = [
                    ('order_id.so_employee_id', '=', line.employee_id.id),
                    ('product_id', '=', line.product_id.id),
                    ('order_id.date_order', '>=', line.target_id.date_from),
                    ('order_id.date_order', '<', line.target_id.date_to + timedelta(days=1)),
                    ('order_id.state', 'in', ['sale', 'done'])
                ]
                sale_lines = self.env['sale.order.line'].search(domain)
                qty = sum(sale_lines.mapped('qty_delivered'))
            line.achieved_target_qty = qty

    @api.depends('target_qty', 'target_id.date_from', 'target_id.date_to', 'achieved_target_qty')
    def _compute_daily_target_qty(self):
        today = date.today()
        for line in self:
            if line.target_id.date_from and line.target_id.date_to and line.target_qty:
                achieved = line.achieved_target_qty or 0.0
                remaining_target = line.target_qty - achieved
                
                if remaining_target <= 0.0:
                    line.daily_target_qty = 0.0
                else:
                    if today < line.target_id.date_from:
                        remaining_days = (line.target_id.date_to - line.target_id.date_from).days + 1
                    else:
                        remaining_days = (line.target_id.date_to - today).days
                    
                    if remaining_days > 0:
                        line.daily_target_qty = math.ceil(remaining_target / remaining_days)
                    elif remaining_days == 0:
                        line.daily_target_qty = math.ceil(remaining_target)
                    else:
                        line.daily_target_qty = 0.0
            else:
                line.daily_target_qty = 0.0


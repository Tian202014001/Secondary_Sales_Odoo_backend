# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"
    
    outlet_route_id = fields.Many2one(
        'sale.route',
        string="Route",
        domain="[('active', '=', True)]",
        help="Route associated with this contact (Outlet)"
    )
    
    distributed_route_ids = fields.One2many(
        'sale.route',
        'distributor_contact_id',
        string="Distributed Routes",
        help="Routes where this contact is the distributor"
    )
    
    so_employee_ids = fields.Many2many(
        'hr.employee',
        'hr_employee_distributor_rel',
        'partner_id',
        'employee_id',
        string="Sales Employees",
        help="Sales employees associated with this distributor contact"
    )

    @api.constrains("customer_type", "outlet_route_id")
    def _check_outlet_route_id(self):
        for partner in self:
            if partner.outlet_route_id and partner.customer_type != "outlet":
                raise ValidationError(_("Route can only be assigned to outlet contacts."))

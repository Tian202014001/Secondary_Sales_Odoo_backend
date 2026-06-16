# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class HrEmployee(models.Model):
    _inherit = "hr.employee"
    
    distributor_contact_ids = fields.Many2many(
        'res.partner',
        'hr_employee_distributor_rel',
        'employee_id',
        'partner_id',
        string="Distributor Contacts",
        domain="[('customer_type', '=', 'distributor')]",
        help="Distributor contacts associated with this employee"
    )
    
    assigned_route_ids = fields.Many2many(
        'sale.route',
        'sale_route_hr_employee_rel',
        'employee_id',
        'route_id',
        string="Assigned Routes",
        help="Routes assigned to this employee"
    )
    
    default_route_id = fields.Many2one(
        "sale.route",
        string="Default Route",
        domain="[('active', '=', True)]",
        help="The recommended default route for this employee."
    )


    @api.constrains("distributor_contact_ids")
    def _check_distributor_contact_ids(self):
        for employee in self:
            for distributor in employee.distributor_contact_ids:
                if distributor.customer_type != "distributor":
                    raise ValidationError(_("Distributor Contact must be a distributor contact."))

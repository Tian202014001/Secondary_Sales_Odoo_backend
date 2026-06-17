# -*- coding: utf-8 -*-

from typing import Required
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class SSRoute(models.Model):
    _name = "sale.route"
    _description = "Route Management"
    _order = "name"

    _sql_constraints = [
        ("code_unique", "unique(code)", "Route Code must be unique."),
    ]

    name = fields.Char(string="Route Name", required=True)
    code = fields.Char(string="Route Code")
    active = fields.Boolean(default=True)
    ss_employee_id = fields.Many2one(
        'hr.employee',
        string="Route Employee",
        help="Employees responsible for this route"
    )
    
    distributor_contact_id = fields.Many2one(
        'res.partner',
        string="Distributor Contact",
        domain="[('customer_type', '=', 'distributor')]",
        help="Distributor contact associated with this route",
    )
    route_line_ids = fields.One2many(
        'sale.route.line',
        'route_id',
        string="Route Outlets",
        help="Ordered outlet visit list for this route"
    )

    @api.constrains("distributor_contact_id")
    def _check_distributor_contact_id(self):
        for route in self:
            if route.distributor_contact_id and route.distributor_contact_id.customer_type != "distributor":
                raise ValidationError(_("Distributor Contact must be a distributor contact."))

# -*- coding: utf-8 -*-

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
    code = fields.Char(string="Route Code", required=True)
    active = fields.Boolean(default=True)
    distributor_contact_id = fields.Many2one(
        'res.partner',
        string="Distributor Contact",
        domain="[('customer_type', '=', 'distributor')]",
        help="Distributor contact associated with this route",
    )
    ss_employee_id = fields.Many2one(
        'hr.employee',
        string="Route Employee",
        domain="[('distributor_contact_ids', 'in', distributor_contact_id)]",
        help="Employees responsible for this route"
    )
    
    route_line_ids = fields.One2many(
        'sale.route.line',
        'route_id',
        string="Route Outlets",
        help="Ordered outlet visit list for this route"
    )
    @api.constrains("code")
    def _check_unique_code(self):
        for route in self:
            if route.code:
                duplicate_count = self.search_count([
                    ("code", "=ilike", route.code.strip()),
                    ("id", "!=", route.id),
                ])
                if duplicate_count > 0:
                    raise ValidationError(_("Route Code '%s' must be unique.") % route.code)

    @api.constrains("distributor_contact_id")
    def _check_distributor_contact_id(self):
        for route in self:
            if route.distributor_contact_id and route.distributor_contact_id.customer_type != "distributor":
                raise ValidationError(_("Distributor Contact must be a distributor contact."))

    @api.constrains("distributor_contact_id", "ss_employee_id")
    def _check_employee_distributor(self):
        for route in self:
            if route.distributor_contact_id and route.ss_employee_id:
                if route.distributor_contact_id not in route.ss_employee_id.distributor_contact_ids:
                    raise ValidationError(_("The selected employee must be assigned to the selected distributor."))

    @api.onchange("distributor_contact_id")
    def _onchange_distributor_contact_id(self):
        if self.distributor_contact_id and self.ss_employee_id:
            if self.distributor_contact_id not in self.ss_employee_id.distributor_contact_ids:
                self.ss_employee_id = False


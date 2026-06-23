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

    effective_distributor_contact_ids = fields.Many2many(
        'res.partner',
        compute="_compute_effective_distributor_contact_ids",
        string="Effective Distributors",
        domain="[('customer_type', '=', 'distributor')]",
        help="Distributor contacts visible to this employee through the hierarchy."
    )
    
    assigned_route_ids = fields.One2many(
        'sale.route',
        'ss_employee_id',
        string="Assigned Routes",
        help="Routes assigned to this employee"
    )
    
    default_route_id = fields.Many2one(
        "sale.route",
        string="Default Route",
        domain="[('active', '=', True)]",
        help="The recommended default route for this employee."
    )

    def _get_effective_distributor_contact_ids(self):
        self.ensure_one()
        if not isinstance(self.id, int):
            return self.distributor_contact_ids.filtered(
                lambda partner: partner.customer_type == "distributor"
            )

        subordinate_employees = self.env["hr.employee"].sudo().search([
            ("id", "child_of", self.id),
        ]) - self
        if subordinate_employees:
            distributors = subordinate_employees.mapped("distributor_contact_ids")
        else:
            distributors = self.distributor_contact_ids
        return distributors.filtered(lambda partner: partner.customer_type == "distributor")

    @api.depends("distributor_contact_ids", "parent_id")
    def _compute_effective_distributor_contact_ids(self):
        for employee in self:
            employee.effective_distributor_contact_ids = [
                (6, 0, employee.sudo()._get_effective_distributor_contact_ids().ids)
            ]


    @api.constrains("distributor_contact_ids")
    def _check_distributor_contact_ids(self):
        for employee in self:
            for distributor in employee.distributor_contact_ids:
                if distributor.customer_type != "distributor":
                    raise ValidationError(_("Distributor Contact must be a distributor contact."))

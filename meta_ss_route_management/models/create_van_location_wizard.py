# -*- coding: utf-8 -*-

from odoo import fields, models

class CreateVanLocationWizard(models.TransientModel):
    _inherit = "create.van.location.wizard"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        domain="[('distributor_contact_ids', 'in', distributor_id)]",
    )

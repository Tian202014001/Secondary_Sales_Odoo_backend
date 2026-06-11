# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StockLocation(models.Model):
    _inherit = "stock.location"

    ss_location_type = fields.Selection(
        selection=[
            ("odoo", "Odoo"),
            ("van_loading", "Van Loading Location"),
        ],
        string="Secondary Sales Location Type",
        default="odoo",
    )
    ss_employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Employee",
    )
    ss_distributor_id = fields.Many2one(
        "res.partner",
        string="Assigned Distributor",
        domain="[('customer_type', '=', 'distributor')]",
    )

    @api.constrains("ss_location_type", "ss_employee_id", "ss_distributor_id")
    def _check_ss_fields_requirement(self):
        for location in self:
            if location.ss_location_type == "van_loading":
                if not location.ss_employee_id:
                    raise ValidationError(_("Assigned Employee is required for Van Loading locations."))
                if not location.ss_distributor_id:
                    raise ValidationError(_("Assigned Distributor is required for Van Loading locations."))

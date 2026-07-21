# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    van_location_count = fields.Integer(
        string="Van Location Count",
        compute="_compute_van_location_count",
    )

    def _compute_van_location_count(self):
        for partner in self:
            if partner.customer_type == "distributor":
                partner.van_location_count = self.env["stock.location"].search_count([
                    ("ss_distributor_id", "=", partner.id),
                    ("ss_location_type", "=", "van_loading"),
                ])
            else:
                partner.van_location_count = 0

    def action_view_van_locations(self):
        self.ensure_one()
        action = {
            "name": "Van Locations",
            "type": "ir.actions.act_window",
            "res_model": "stock.location",
            "view_mode": "list,form",
            "domain": [
                ("ss_distributor_id", "=", self.id),
                ("ss_location_type", "=", "van_loading"),
            ],
            "context": {
                "default_ss_distributor_id": self.id,
                "default_ss_location_type": "van_loading",
                "default_usage": "customer",
            },
        }
        return action

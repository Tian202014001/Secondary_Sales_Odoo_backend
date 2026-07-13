# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class StockLocation(models.Model):
    _inherit = "stock.location"

    ss_location_type = fields.Selection(
        selection=[
            ("odoo", "Odoo"),
            ("distributor_location", "Distributor Location"),
            ("van_loading", "Van Loading Location"),
        ],
        string="Secondary Sales Location Type",
        default="odoo",
    )
    ss_employee_id = fields.Many2one(
        "hr.employee",
        string="Assigned Employee",
        domain="[('distributor_contact_ids', 'in', ss_distributor_id)]",
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
                if location.ss_distributor_id not in location.ss_employee_id.distributor_contact_ids:
                    raise ValidationError(_("The assigned employee must be assigned to the selected distributor."))

    @api.onchange("ss_location_type", "ss_distributor_id")
    def _onchange_van_loading_parent(self):
        if self.ss_location_type == "van_loading" and self.ss_distributor_id:
            if self.ss_distributor_id.property_stock_customer:
                self.location_id = self.ss_distributor_id.property_stock_customer
                self.usage = "customer"
            if self.ss_employee_id and self.ss_distributor_id not in self.ss_employee_id.distributor_contact_ids:
                self.ss_employee_id = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("ss_location_type") == "van_loading" and vals.get("ss_distributor_id"):
                if not vals.get("location_id"):
                    distributor = self.env["res.partner"].browse(vals["ss_distributor_id"])
                    if distributor.property_stock_customer:
                        vals["location_id"] = distributor.property_stock_customer.id
                        vals["usage"] = "customer"

        locations = super().create(vals_list)
        for location in locations:
            if location.ss_location_type == 'van_loading' and not location.scrap_location:
                location._ensure_van_scrap_sibling()
        return locations

    def _ensure_van_scrap_sibling(self):
        """Create the paired scrap location for a van under the distributor's scrap location."""
        self.ensure_one()
        import re
        van_name = re.sub(r'(?i)\s*-\s*stock\s*$', '', self.name)
        scrap_name = "%s - Scrap" % van_name

        # Determine the parent location for the van scrap
        parent_id = self.location_id.id
        if self.ss_distributor_id and 'scrap_location_id' in self.ss_distributor_id._fields:
            if self.ss_distributor_id.scrap_location_id:
                parent_id = self.ss_distributor_id.scrap_location_id.id

        existing = self.env["stock.location"].search([
            ("name", "=", scrap_name),
            ("location_id", "=", parent_id),
            ("active", "=", True),
        ], limit=1)
        
        if not existing:
            scrap_loc = self.env["stock.location"].create({
                "name": scrap_name,
                "location_id": parent_id,
                "usage": "customer",
                "scrap_location": True,
                "ss_location_type": "van_loading",
                "ss_employee_id": self.ss_employee_id.id if self.ss_employee_id else False,
                "ss_distributor_id": self.ss_distributor_id.id if self.ss_distributor_id else False,
            })
            scrap_loc._compute_complete_name()
            scrap_loc.flush_recordset(["complete_name"])
        return True

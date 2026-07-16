# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class CreateVanLocationWizard(models.TransientModel):
    _name = "create.van.location.wizard"
    _description = "Create Van Location Wizard"

    distributor_id = fields.Many2one(
        "res.partner",
        string="Distributor",
        required=True,
        domain="[('customer_type', '=', 'distributor')]",
    )
    ss_location_type = fields.Selection(
        selection=[
            ("distributor_location", "Distributor Location"),
            ("van_loading", "Van Loading Location"),
        ],
        string="Location Type",
        default="van_loading",
        required=True,
    )
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=False,
    )
    name = fields.Char(string="Location Name", required=True, readonly=True)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        distributor_id = res.get("distributor_id") or self._context.get("default_distributor_id")
        ss_location_type = res.get("ss_location_type", "van_loading")
        
        if distributor_id and ss_location_type == "van_loading" and "name" in fields_list:
            distributor = self.env["res.partner"].browse(distributor_id)
            res["name"] = self._generate_next_van_name(distributor)
        return res

    @api.onchange("distributor_id", "ss_location_type")
    def _onchange_distributor_or_type(self):
        if self.ss_location_type == "van_loading" and self.distributor_id:
            self.name = self._generate_next_van_name(self.distributor_id)
        else:
            self.name = False
            self.employee_id = False

    def _generate_next_van_name(self, distributor):
        import re
        existing_vans = self.env["stock.location"].search([
            ("ss_distributor_id", "=", distributor.id),
            ("ss_location_type", "=", "van_loading"),
            ("scrap_location", "=", False),
        ])
        
        max_seq = 0
        for van in existing_vans:
            match = re.search(r'-van-(\d+)$', van.name)
            if match:
                try:
                    seq = int(match.group(1))
                    if seq > max_seq:
                        max_seq = seq
                except ValueError:
                    pass
        
        next_seq = (max_seq or len(existing_vans)) + 1
        return f"{distributor.name}-van-{next_seq:03d}"

    def action_create_van_location(self):
        self.ensure_one()
        distributor = self.distributor_id
        if not distributor.property_stock_customer:
            raise ValidationError(_("The selected distributor does not have a customer stock location configured."))

        if self.ss_location_type == "van_loading" and not self.employee_id:
            raise ValidationError(_("Employee is required for Van Loading Location."))

        StockLocation = self.env['stock.location'].sudo()
        vals = {
            'name': self.name,
            'location_id': distributor.property_stock_customer.id,
            'usage': 'customer',
            'ss_location_type': self.ss_location_type,
            'ss_distributor_id': distributor.id,
        }
        if self.ss_location_type == "van_loading":
            vals['ss_employee_id'] = self.employee_id.id

        new_location = StockLocation.create(vals)
        new_location._compute_complete_name()
        new_location.flush_recordset(['complete_name'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Location "%s" has been created.') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

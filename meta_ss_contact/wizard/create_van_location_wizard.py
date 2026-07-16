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
    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
    )
    name = fields.Char(string="Van Location Name", required=True)

    def action_create_van_location(self):
        self.ensure_one()
        distributor = self.distributor_id
        if not distributor.property_stock_customer:
            raise ValidationError(_("The selected distributor does not have a customer stock location configured."))

        StockLocation = self.env['stock.location'].sudo()
        vals = {
            'name': self.name,
            'location_id': distributor.property_stock_customer.id,
            'usage': 'customer',
        }
        if 'ss_location_type' in StockLocation._fields:
            vals['ss_location_type'] = 'van_loading'
        if 'ss_employee_id' in StockLocation._fields:
            vals['ss_employee_id'] = self.employee_id.id
        if 'ss_distributor_id' in StockLocation._fields:
            vals['ss_distributor_id'] = distributor.id

        new_location = StockLocation.create(vals)
        new_location._compute_complete_name()
        new_location.flush_recordset(['complete_name'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Van Location "%s" and its scrap sibling have been created.') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }

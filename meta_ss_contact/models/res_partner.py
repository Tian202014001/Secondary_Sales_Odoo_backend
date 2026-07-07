# -*- coding: utf-8 -*-

from odoo import api, fields, models

class ResPartner(models.Model):
    _inherit = "res.partner"

    customer_type = fields.Selection(
        selection=[
           ('distributor','Distributor'),
           ('outlet','Outlet'),
        ],
        string="Customer Type",
        default=False,
    )
    
    scrap_location_id = fields.Many2one(
        'stock.location',
        string='Scrap Location',
        help='Scrap location for the partner'
    )

    db_code = fields.Char(string='DB Code', store=True)
    
    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        for partner in partners:
            if partner.customer_type == 'distributor':
                partner._ensure_distributor_locations()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if 'customer_type' in vals and vals['customer_type'] == 'distributor':
            for partner in self:
                partner._ensure_distributor_locations()
        return res

    def _ensure_distributor_locations(self):
        """Create and assign stock locations for a distributor."""
        self.ensure_one()
        if self.customer_type != 'distributor':
            return False

        StockLocation = self.env['stock.location'].sudo()
        customer_parent = self.env.ref('stock.stock_location_customers')

        # Find or create dealer location
        dealer_loc = StockLocation.search([
            ('name', '=', self.name),
            ('usage', '=', 'customer'),
            ('location_id', '=', customer_parent.id),
            ('active', '=', True)
        ], limit=1)
        if not dealer_loc:
            vals = {
                'name': self.name,
                'usage': 'customer',
                'location_id': customer_parent.id,
            }
            if 'ss_location_type' in StockLocation._fields:
                vals['ss_location_type'] = 'distributor_location'
            if 'ss_distributor_id' in StockLocation._fields:
                vals['ss_distributor_id'] = self.id
                
            dealer_loc = StockLocation.create(vals)
            dealer_loc._compute_complete_name()
            dealer_loc.flush_recordset(['complete_name'])
        else:
            update_vals = {}
            if 'ss_location_type' in StockLocation._fields and dealer_loc.ss_location_type != 'distributor_location':
                update_vals['ss_location_type'] = 'distributor_location'
            if 'ss_distributor_id' in StockLocation._fields and dealer_loc.ss_distributor_id.id != self.id:
                update_vals['ss_distributor_id'] = self.id
            if update_vals:
                dealer_loc.write(update_vals)

        # Assign dealer_loc as the customer location
        if not self.property_stock_customer or self.property_stock_customer == customer_parent:
            self.sudo().property_stock_customer = dealer_loc

        # Find or create Scrap location directly under partner/customer
        has_scrap_field = 'scrap_location_id' in self._fields
        if has_scrap_field and not self.scrap_location_id:
            scrap_name = f"{self.name} - Scrap"
            scrap_loc = StockLocation.search([
                ('name', '=', scrap_name),
                ('usage', '=', 'customer'),
                ('location_id', '=', customer_parent.id),
                ('active', '=', True),
                ('scrap_location', '=', True)
            ], limit=1)
            if not scrap_loc:
                vals = {
                    'name': scrap_name,
                    'usage': 'customer',
                    'location_id': customer_parent.id,
                    'scrap_location': True,
                }
                if 'ss_location_type' in StockLocation._fields:
                    vals['ss_location_type'] = 'distributor_location'
                if 'ss_distributor_id' in StockLocation._fields:
                    vals['ss_distributor_id'] = self.id
                    
                scrap_loc = StockLocation.create(vals)
                scrap_loc._compute_complete_name()
                scrap_loc.flush_recordset(['complete_name'])
            else:
                update_vals = {}
                if 'ss_location_type' in StockLocation._fields and scrap_loc.ss_location_type != 'distributor_location':
                    update_vals['ss_location_type'] = 'distributor_location'
                if 'ss_distributor_id' in StockLocation._fields and scrap_loc.ss_distributor_id.id != self.id:
                    update_vals['ss_distributor_id'] = self.id
                if update_vals:
                    scrap_loc.write(update_vals)
                    
            self.sudo().scrap_location_id = scrap_loc

        return True
    
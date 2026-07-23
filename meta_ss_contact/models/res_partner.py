# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class ResPartner(models.Model):
    _inherit = "res.partner"

    _sql_constraints = [
        ('db_code_unique', 'unique(db_code)', 'DB Code must be unique.'),
    ]

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

    @api.constrains("db_code")
    def _check_unique_db_code(self):
        for partner in self:
            if partner.db_code:
                duplicate_count = self.search_count([
                    ("db_code", "=ilike", partner.db_code.strip()),
                    ("id", "!=", partner.id),
                ])
                if duplicate_count > 0:
                    raise ValidationError(_("DB Code '%s' must be unique.") % partner.db_code)

    @api.depends('db_code')
    def _compute_display_name(self):
        super()._compute_display_name()
        for partner in self:
            if partner.db_code:
                partner.display_name = f"[{partner.db_code}] {partner.display_name}"

    @api.model
    def _name_search(self, name, domain=None, operator='ilike', limit=100, order=None):
        domain = domain or []
        if name:
            partners = self.search([('db_code', operator, name)] + domain, limit=limit, order=order)
            ids = list(partners.ids)
            if len(ids) < limit:
                sub_domain = [('id', 'not in', ids)] + domain
                search_ids = super()._name_search(name, domain=sub_domain, operator=operator, limit=limit - len(ids), order=order)
                if search_ids:
                    if isinstance(search_ids, models.BaseModel):
                        ids.extend(search_ids.ids)
                    else:
                        ids.extend(list(search_ids))
            return ids
        return super()._name_search(name, domain=domain, operator=operator, limit=limit, order=order)

    
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
    
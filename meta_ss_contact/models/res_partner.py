# -*- coding: utf-8 -*-

from odoo import fields, models

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
    
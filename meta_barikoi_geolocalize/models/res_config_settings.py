# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    barikoi_auto_geocode_partners = fields.Boolean(
        string='Auto Geocode Partners',
        config_parameter='barikoi.auto_geocode_partners',
        default=False,
        help='Automatically geocode partner addresses when created or updated'
    )
    
    barikoi_nearby_distance_threshold = fields.Float(
        string='Nearby Distance Threshold (km)',
        config_parameter='barikoi.nearby_distance_threshold',
        default=10.0,
        help='Maximum distance in kilometers to consider a partner as nearby'
    )
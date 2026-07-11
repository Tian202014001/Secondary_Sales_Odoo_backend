# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    barikoi_autocomplete_min_chars = fields.Integer(
        string='Minimum Characters for Autocomplete',
        config_parameter='barikoi.autocomplete_min_chars',
        default=3,
        help='Minimum number of characters to type before autocomplete suggestions appear'
    )
    
    barikoi_autocomplete_limit = fields.Integer(
        string='Autocomplete Suggestions Limit',
        config_parameter='barikoi.autocomplete_limit',
        default=10,
        help='Maximum number of autocomplete suggestions to show'
    )
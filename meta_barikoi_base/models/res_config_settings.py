# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Barikoi API Configuration
    barikoi_api_key = fields.Char(
        string='Barikoi API Key',
        config_parameter='barikoi.api_key',
        help="Your Barikoi API Key. Get one at https://barikoi.com"
    )
    
    barikoi_enabled = fields.Boolean(
        string='Enable Barikoi Maps',
        config_parameter='barikoi.enabled',
        default=False,
        help="Enable Barikoi Maps as an alternative to Google Maps"
    )
    
    barikoi_default_provider = fields.Boolean(
        string='Use Barikoi as Default Map Provider',
        config_parameter='barikoi.default_provider',
        default=False,
        help="Use Barikoi as the default map provider instead of Google Maps"
    )
    
    # Bangladesh specific settings
    barikoi_bangladesh_fields = fields.Boolean(
        string='Enable Bangladesh Address Fields',
        config_parameter='barikoi.bangladesh_fields',
        default=True,
        help="Enable Bangladesh-specific address fields (Division, District, Upazila, Union)"
    )
    
    barikoi_map_style = fields.Selection(
        [
            ('default', 'Default'),
            ('dark', 'Dark'),
            ('light', 'Light'),
            ('satellite', 'Satellite'),
        ],
        string='Barikoi Map Style',
        config_parameter='barikoi.map_style',
        default='default',
        help="Default map style for Barikoi maps"
    )

    @api.onchange('barikoi_enabled')
    def _onchange_barikoi_enabled(self):
        """Clear API key when Barikoi is disabled"""
        if not self.barikoi_enabled:
            self.barikoi_default_provider = False

    def action_test_barikoi_connection(self):
        """Test the Barikoi API connection"""
        self.ensure_one()
        if not self.barikoi_api_key:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Please enter a Barikoi API Key first.'),
                    'type': 'danger',
                    'sticky': False,
                }
            }
        
        # Test the API key by making a simple request
        try:
            api = self.env['barikoi.api']
            result = api.test_connection()
            
            if result.get('status') == 'success':
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Barikoi API connection successful!'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Error'),
                        'message': result.get('message', _('Failed to connect to Barikoi API')),
                        'type': 'danger',
                        'sticky': False,
                    }
                }
        except Exception as e:
            _logger.error("Barikoi API test failed: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Connection failed: %s') % str(e),
                    'type': 'danger',
                    'sticky': False,
                }
            }
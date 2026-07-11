# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_open_map(self):
        """Open partner location on Barikoi web map (Community Edition)"""
        self.ensure_one()
        
        if not self.partner_latitude or not self.partner_longitude:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Coordinates'),
                    'message': _('Please geocode this partner first to view on map.'),
                    'type': 'warning',
                }
            }
        
        # Build map URL with place code and coordinates
        # Format: https://maps.barikoi.com/?place={uCode}#16/{lat}/{lon}
        # The place parameter shows the place name/code, coordinates for map position
        
        base_url = "https://maps.barikoi.com/"
        
        # Always include coordinates in the hash
        coord_hash = f"#16/{self.partner_latitude}/{self.partner_longitude}"
        
        if self.barikoi_ucode:
            # Include place code as query parameter
            map_url = f"{base_url}?place={self.barikoi_ucode}{coord_hash}"
        else:
            # Just coordinates
            map_url = f"{base_url}{coord_hash}"
        
        _logger.info("Barikoi: Opening map URL: %s", map_url)
        
        return {
            'type': 'ir.actions.act_url',
            'url': map_url,
            'target': 'new',
        }

    def action_show_on_map(self):
        """Action to show partner on map - opens Barikoi web map"""
        return self.action_open_map()
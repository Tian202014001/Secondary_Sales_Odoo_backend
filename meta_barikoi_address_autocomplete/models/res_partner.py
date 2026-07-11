# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

# Bangladesh District to Division Mapping
# This mapping is used when Barikoi autocomplete doesn't return division
DISTRICT_TO_DIVISION = {
    # Barishal Division
    'Barguna': 'Barishal',
    'Barisal': 'Barishal',
    'Bhola': 'Barishal',
    'Jhalokati': 'Barishal',
    'Patuakhali': 'Barishal',
    'Pirojpur': 'Barishal',
    # Chattogram Division
    'Bandarban': 'Chattogram',
    'Brahmanbaria': 'Chattogram',
    'Chandpur': 'Chattogram',
    'Chittagong': 'Chattogram',
    'Comilla': 'Chattogram',
    "Cox's Bazar": 'Chattogram',
    'Feni': 'Chattogram',
    'Khagrachhari': 'Chattogram',
    'Lakshmipur': 'Chattogram',
    'Noakhali': 'Chattogram',
    'Rangamati': 'Chattogram',
    # Dhaka Division
    'Dhaka': 'Dhaka',
    'Faridpur': 'Dhaka',
    'Gazipur': 'Dhaka',
    'Gopalganj': 'Dhaka',
    'Kishoreganj': 'Dhaka',
    'Madaripur': 'Dhaka',
    'Manikganj': 'Dhaka',
    'Munshiganj': 'Dhaka',
    'Narayanganj': 'Dhaka',
    'Narsingdi': 'Dhaka',
    'Rajbari': 'Dhaka',
    'Shariatpur': 'Dhaka',
    'Tangail': 'Dhaka',
    # Khulna Division
    'Bagerhat': 'Khulna',
    'Chuadanga': 'Khulna',
    'Jessore': 'Khulna',
    'Jhenaidah': 'Khulna',
    'Khulna': 'Khulna',
    'Kushtia': 'Khulna',
    'Magura': 'Khulna',
    'Meherpur': 'Khulna',
    'Narail': 'Khulna',
    'Satkhira': 'Khulna',
    # Mymensingh Division
    'Jamalpur': 'Mymensingh',
    'Mymensingh': 'Mymensingh',
    'Netrokona': 'Mymensingh',
    'Sherpur': 'Mymensingh',
    # Rajshahi Division
    'Bogra': 'Rajshahi',
    'Joypurhat': 'Rajshahi',
    'Naogaon': 'Rajshahi',
    'Natore': 'Rajshahi',
    'Nawabganj': 'Rajshahi',
    'Pabna': 'Rajshahi',
    'Rajshahi': 'Rajshahi',
    'Sirajganj': 'Rajshahi',
    # Rangpur Division
    'Dinajpur': 'Rangpur',
    'Gaibandha': 'Rangpur',
    'Kurigram': 'Rangpur',
    'Lalmonirhat': 'Rangpur',
    'Nilphamari': 'Rangpur',
    'Panchagarh': 'Rangpur',
    'Rangpur': 'Rangpur',
    'Thakurgaon': 'Rangpur',
    # Sylhet Division
    'Habiganj': 'Sylhet',
    'Moulvibazar': 'Sylhet',
    'Sunamganj': 'Sylhet',
    'Sylhet': 'Sylhet',
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # Bangladesh-specific address fields from Barikoi
    barikoi_division = fields.Char(
        string='Division',
        help='Bangladesh Division (Administrative Level 1)'
    )
    barikoi_district = fields.Char(
        string='District',
        help='Bangladesh District (Administrative Level 2)'
    )
    barikoi_upazila = fields.Char(
        string='Upazila',
        help='Bangladesh Upazila/Sub-District (Administrative Level 3)'
    )
    barikoi_union = fields.Char(
        string='Union',
        help='Bangladesh Union (Administrative Level 4)'
    )
    barikoi_place_id = fields.Char(
        string='Barikoi Place ID',
        help='Reference ID from Barikoi database'
    )
    barikoi_ucode = fields.Char(
        string='Barikoi uCode',
        help='Unique place code from Barikoi for direct map linking (e.g., BKOI54094)'
    )

    @api.model
    def _get_barikoi_address_fields(self):
        """Return list of fields that can be populated from Barikoi API"""
        return [
            'street', 'street2', 'city', 'zip',
            'partner_latitude', 'partner_longitude',
            'barikoi_division', 'barikoi_district',
            'barikoi_upazila', 'barikoi_union',
            'barikoi_place_id', 'barikoi_ucode', 'country_id'
        ]

    def action_geocode_address(self):
        """
        Geocode the current address using Barikoi API.
        This method can be called from a button in the partner form.
        """
        self.ensure_one()
        
        # Check if Barikoi is enabled
        if not self.env['ir.config_parameter'].sudo().get_param('barikoi.enabled') == 'True':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Barikoi Not Enabled'),
                    'message': _('Please enable Barikoi in Settings first.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        # Build address string for geocoding
        address_parts = []
        if self.street:
            address_parts.append(self.street)
        if self.street2:
            address_parts.append(self.street2)
        if self.city:
            address_parts.append(self.city)
        if self.barikoi_district:
            address_parts.append(self.barikoi_district)
        if self.barikoi_division:
            address_parts.append(self.barikoi_division)
        
        if not address_parts:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Address'),
                    'message': _('Please enter an address first.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        address = ', '.join(address_parts)
        
        try:
            api = self.env['barikoi.api']
            result = api.geocode(address)
            
            if result and 'place' in result:
                place = result['place']
                self.write({
                    'partner_latitude': place.get('latitude'),
                    'partner_longitude': place.get('longitude'),
                    'barikoi_place_id': str(place.get('id')) if place.get('id') else False,
                    'barikoi_ucode': place.get('uCode'),
                })
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Address geocoded successfully.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Not Found'),
                        'message': _('Could not find coordinates for this address.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
        except Exception as e:
            _logger.error("Barikoi geocoding error: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Geocoding failed: %s') % str(e),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def action_reverse_geocode(self):
        """
        Reverse geocode the current coordinates to get address details.
        This method can be called from a button in the partner form.
        """
        self.ensure_one()
        
        # Check if Barikoi is enabled
        if not self.env['ir.config_parameter'].sudo().get_param('barikoi.enabled') == 'True':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Barikoi Not Enabled'),
                    'message': _('Please enable Barikoi in Settings first.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        if not self.partner_latitude or not self.partner_longitude:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Coordinates'),
                    'message': _('Please set latitude and longitude first.'),
                    'type': 'warning',
                    'sticky': False,
                }
            }
        
        try:
            api = self.env['barikoi.api']
            result = api.reverse_geocode(
                self.partner_latitude,
                self.partner_longitude
            )
            
            if result and 'place' in result:
                place = result['place']
                address_data = api.parse_address_components(place)
                self.write(address_data)
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Success'),
                        'message': _('Address updated from coordinates.'),
                        'type': 'success',
                        'sticky': False,
                    }
                }
            else:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Not Found'),
                        'message': _('Could not find address for these coordinates.'),
                        'type': 'warning',
                        'sticky': False,
                    }
                }
        except Exception as e:
            _logger.error("Barikoi reverse geocoding error: %s", str(e))
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Reverse geocoding failed: %s') % str(e),
                    'type': 'danger',
                    'sticky': False,
                }
            }

    def update_from_barikoi_place(self, place_data):
        """
        Update partner record from Barikoi place data
        
        Args:
            place_data (dict): Place data from Barikoi API
        """
        self.ensure_one()
        
        api = self.env['barikoi.api']
        address_data = api.parse_address_components(place_data)
        
        # Save Barikoi identifiers
        if place_data.get('id'):
            address_data['barikoi_place_id'] = str(place_data['id'])
        if place_data.get('uCode'):
            address_data['barikoi_ucode'] = place_data['uCode']
        
        self.write(address_data)

    def update_from_barikoi_suggestion(self, suggestion):
        """
        Update partner record from Barikoi autocomplete suggestion.
        This method is called from the JS widget to update all fields atomically.
        
        Args:
            suggestion (dict): Suggestion data from autocomplete widget
        
        Returns:
            dict: Updated values including country_id and state_id with display names
        """
        _logger.info("Barikoi: update_from_barikoi_suggestion called with: %s", suggestion)
        
        result = {}
        
        for partner in self:
            values = {}
            
            # Street address
            if suggestion.get('label') or suggestion.get('name'):
                values['street'] = suggestion.get('label') or suggestion.get('name')
            
            # City - use district as city (Bangladesh mapping)
            if suggestion.get('district'):
                values['city'] = suggestion['district']
            elif suggestion.get('city'):
                values['city'] = suggestion['city']
            
            # ZIP/Postcode
            if suggestion.get('post_code'):
                values['zip'] = str(suggestion['post_code'])
            
            # Street2 - area
            if suggestion.get('area'):
                values['street2'] = suggestion['area']
            
            # Coordinates - CRITICAL: These must be float values
            if suggestion.get('latitude') is not None:
                try:
                    lat = float(suggestion['latitude'])
                    _logger.info("Barikoi: Setting latitude to %s", lat)
                    values['partner_latitude'] = lat
                except (ValueError, TypeError) as e:
                    _logger.warning("Barikoi: Could not parse latitude: %s", e)
            
            if suggestion.get('longitude') is not None:
                try:
                    lng = float(suggestion['longitude'])
                    _logger.info("Barikoi: Setting longitude to %s", lng)
                    values['partner_longitude'] = lng
                except (ValueError, TypeError) as e:
                    _logger.warning("Barikoi: Could not parse longitude: %s", e)
            
            # Barikoi-specific fields
            if suggestion.get('division'):
                values['barikoi_division'] = suggestion['division']
            if suggestion.get('district'):
                values['barikoi_district'] = suggestion['district']
            if suggestion.get('sub_district'):
                values['barikoi_upazila'] = suggestion['sub_district']
            if suggestion.get('id'):
                values['barikoi_place_id'] = str(suggestion['id'])
            if suggestion.get('uCode'):
                values['barikoi_ucode'] = suggestion['uCode']
            
            # Set country to Bangladesh
            bangladesh = self.env['res.country'].search([('code', '=', 'BD')], limit=1)
            if bangladesh:
                values['country_id'] = bangladesh.id
                result['country_id'] = {
                    'id': bangladesh.id,
                    'display_name': bangladesh.name,
                }
                
                # In Bangladesh, Odoo states are DIVISIONS
                # Barikoi autocomplete API doesn't return division, so we use district-to-division mapping
                district_name = suggestion.get('district', '')
                division_name = suggestion.get('division', '') or DISTRICT_TO_DIVISION.get(district_name, '')
                
                _logger.info("Barikoi: District '%s' maps to Division '%s'", district_name, division_name)
                
                if division_name:
                    # First try exact match
                    state = self.env['res.country.state'].search([
                        ('name', '=', division_name),
                        ('country_id', '=', bangladesh.id)
                    ], limit=1)
                    _logger.info("Barikoi: Exact match search result: %s", state.name if state else "Not found")
                    
                    # If no exact match, try ilike (case-insensitive)
                    if not state:
                        state = self.env['res.country.state'].search([
                            ('name', 'ilike', division_name),
                            ('country_id', '=', bangladesh.id)
                        ], limit=1)
                        _logger.info("Barikoi: ILIKE match search result: %s", state.name if state else "Not found")
                    
                    if state:
                        values['state_id'] = state.id
                        result['state_id'] = {
                            'id': state.id,
                            'display_name': state.name,
                        }
                        values['barikoi_division'] = division_name
                        result['barikoi_division'] = division_name
                        _logger.info("Barikoi: Found matching state: %s (id=%s) for division: '%s'", 
                                    state.name, state.id, division_name)
                    else:
                        _logger.warning("Barikoi: No matching state found for division: '%s'", division_name)
                else:
                    _logger.warning("Barikoi: Could not determine division for district: '%s'", district_name)
            
            _logger.info("Barikoi: Writing values to partner %s: %s", partner.id, values)
            partner.write(values)
        
        # Return the updated values for the form to refresh
        result['street'] = suggestion.get('label') or suggestion.get('name', '')
        # City - use district as city (Bangladesh mapping)
        result['city'] = suggestion.get('district') or suggestion.get('city', '')
        if suggestion.get('post_code'):
            result['zip'] = str(suggestion['post_code'])
        if suggestion.get('area'):
            result['street2'] = suggestion['area']
        if suggestion.get('latitude'):
            result['partner_latitude'] = float(suggestion['latitude'])
        if suggestion.get('longitude'):
            result['partner_longitude'] = float(suggestion['longitude'])
        if suggestion.get('division'):
            result['barikoi_division'] = suggestion['division']
        if suggestion.get('district'):
            result['barikoi_district'] = suggestion['district']
        if suggestion.get('sub_district'):
            result['barikoi_upazila'] = suggestion['sub_district']
        if suggestion.get('id'):
            result['barikoi_place_id'] = str(suggestion['id'])
        if suggestion.get('uCode'):
            result['barikoi_ucode'] = suggestion['uCode']
        
        return result

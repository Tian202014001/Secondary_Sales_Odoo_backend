# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import math

from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    geolocalize_on_write = fields.Boolean(
        string='Auto Geolocalize',
        compute='_compute_geolocalize_on_write',
        help='Automatically geolocalize when address changes'
    )
    last_geocoding_date = fields.Datetime(
        string='Last Geocoded',
        readonly=True,
        help='Last time coordinates were updated'
    )
    geocoding_status = fields.Selection([
        ('not_geocoded', 'Not Geocoded'),
        ('geocoded', 'Geocoded'),
        ('failed', 'Geocoding Failed'),
    ], string='Geocoding Status', default='not_geocoded',
        help='Status of address geocoding')
    
    has_valid_coordinates = fields.Boolean(
        string='Has Coordinates',
        compute='_compute_has_valid_coordinates',
        store=True,
        help='Technical field to check if partner has valid coordinates'
    )
    
    @api.depends('partner_latitude', 'partner_longitude')
    def _compute_has_valid_coordinates(self):
        """Check if partner has valid coordinates"""
        for partner in self:
            partner.has_valid_coordinates = (
                partner.partner_latitude and partner.partner_longitude and
                partner.partner_latitude != 0.0 and partner.partner_longitude != 0.0
            )
    
    @api.depends()
    def _compute_geolocalize_on_write(self):
        """Check if auto-geolocalization is enabled"""
        auto_geocode = self.env['ir.config_parameter'].sudo().get_param(
            'barikoi.auto_geocode_partners', 'False'
        ) == 'True'
        for partner in self:
            partner.geolocalize_on_write = auto_geocode

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to set initial geocoding status"""
        for vals in vals_list:
            # Set geocoding status based on coordinates
            lat = vals.get('partner_latitude')
            lng = vals.get('partner_longitude')
            if lat and lng and lat != 0.0 and lng != 0.0:
                vals['geocoding_status'] = 'geocoded'
        partners = super().create(vals_list)
        return partners

    def write(self, vals):
        """
        Override write to prevent base_geolocalize from resetting coordinates.
        
        The base_geolocalize module resets partner_latitude/partner_longitude to 0.0
        when address fields change without coordinates. We prevent this when:
        1. Barikoi is enabled (we manage coordinates ourselves)
        2. Coordinates are being explicitly set via barikoi_geocoding context
        """
        # Check if this is a Barikoi geocoding write - if so, let it through
        is_barikoi_geocoding = self.env.context.get('barikoi_geocoding', False)
        
        if is_barikoi_geocoding:
            # Direct coordinate update from Barikoi - bypass all other write() overrides
            # by calling the base res.partner write directly via SQL to avoid base_geolocalize resetting coords
            _logger.info("Barikoi: write() with barikoi_geocoding context, vals=%s", vals)
            # Use direct SQL to bypass base_geolocalize which might reset coordinates
            self._update_coordinates_direct(vals)
            return True
        
        # Check if Barikoi is enabled
        barikoi_enabled = self.env['ir.config_parameter'].sudo().get_param('barikoi.enabled') == 'True'
        
        if barikoi_enabled:
            # When Barikoi is enabled, preserve coordinates on address changes
            # base_geolocalize would reset them to 0.0, but we want to keep them
            address_fields = {'street', 'zip', 'city', 'state_id', 'country_id'}
            if any(field in vals for field in address_fields):
                # If coordinates are not being explicitly set, preserve existing values
                if 'partner_latitude' not in vals and 'partner_longitude' not in vals:
                    # Preserve existing coordinates for all records being updated
                    # by including them in vals so base_geolocalize doesn't reset them
                    for partner in self:
                        if partner.partner_latitude and partner.partner_longitude:
                            # Only preserve if they have valid coordinates
                            vals['partner_latitude'] = partner.partner_latitude
                            vals['partner_longitude'] = partner.partner_longitude
                            break  # Only need to set once in vals
        
        # Update geocoding status when coordinates change
        if 'partner_latitude' in vals or 'partner_longitude' in vals:
            lat = vals.get('partner_latitude')
            lng = vals.get('partner_longitude')
            if lat and lng and lat != 0.0 and lng != 0.0:
                vals['geocoding_status'] = 'geocoded'
                vals['last_geocoding_date'] = fields.Datetime.now()
            elif lat is False or lng is False:
                vals['geocoding_status'] = 'not_geocoded'
        
        result = super().write(vals)
        return result

    def action_geocode_address(self):
        """Geocode the partner address using Barikoi API"""
        self.ensure_one()
        
        _logger.info("Barikoi: action_geocode_address called for partner %s", self.id)
        
        # Check if Barikoi is enabled
        if not self.env['ir.config_parameter'].sudo().get_param('barikoi.enabled') == 'True':
            _logger.warning("Barikoi: Barikoi not enabled in settings")
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Barikoi Not Enabled'),
                    'message': _('Please enable Barikoi in Settings first.'),
                    'type': 'warning',
                }
            }
        
        # Build address string
        address_parts = []
        if self.street:
            address_parts.append(self.street)
        if self.street2:
            address_parts.append(self.street2)
        if self.city:
            address_parts.append(self.city)
        if self.zip:
            address_parts.append(self.zip)
        
        if not address_parts:
            _logger.warning("Barikoi: No address provided for partner %s", self.id)
            self.geocoding_status = 'failed'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Address'),
                    'message': _('Please enter an address first.'),
                    'type': 'warning',
                }
            }
        
        address = ', '.join(address_parts)
        _logger.info("Barikoi: Geocoding address for partner %s: %s", self.id, address)
        
        try:
            api = self.env['barikoi.api']
            result = api.geocode(address)
            
            _logger.info("Barikoi: Geocode result for partner %s: %s", self.id, result)
            
            if result and 'place' in result and result['place']:
                place = result['place']
                lat = place.get('latitude')
                lon = place.get('longitude')
                
                _logger.info("Barikoi: Extracted coordinates for partner %s: lat=%s, lon=%s", 
                            self.id, lat, lon)
                
                if lat and lon and lat != 0.0 and lon != 0.0:
                    update_vals = {
                        'partner_latitude': lat,
                        'partner_longitude': lon,
                        'geocoding_status': 'geocoded',
                        'last_geocoding_date': fields.Datetime.now(),
                    }
                    if place.get('id'):
                        update_vals['barikoi_place_id'] = str(place['id'])
                    if place.get('uCode'):
                        update_vals['barikoi_ucode'] = place['uCode']
                    
                    _logger.info("Barikoi: Writing coordinates to partner %s: %s", self.id, update_vals)
                    # Use context to bypass base_geolocalize which might reset coordinates
                    self.with_context(barikoi_geocoding=True).write(update_vals)
                    
                    _logger.info("Barikoi: Successfully geocoded partner %s to lat=%s, lon=%s", 
                                self.id, lat, lon)
                    
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Success'),
                            'message': _('Address geocoded successfully. Coordinates: %s, %s') % (lat, lon),
                            'type': 'success',
                        }
                    }
                else:
                    _logger.warning("Barikoi: Invalid coordinates returned for partner %s: lat=%s, lon=%s", 
                                   self.id, lat, lon)
                    self.geocoding_status = 'failed'
                    return {
                        'type': 'ir.actions.client',
                        'tag': 'display_notification',
                        'params': {
                            'title': _('Invalid Coordinates'),
                            'message': _('Geocoding returned invalid coordinates.'),
                            'type': 'warning',
                        }
                    }
            else:
                _logger.warning("Barikoi: No place found in geocode result for partner %s", self.id)
                self.geocoding_status = 'failed'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Not Found'),
                        'message': _('Could not find coordinates for this address.'),
                        'type': 'warning',
                    }
                }
        except Exception as e:
            _logger.error("Barikoi geocoding error for partner %s: %s", self.id, str(e))
            self.geocoding_status = 'failed'
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('Geocoding failed: %s') % str(e),
                    'type': 'danger',
                }
            }

    def action_batch_geocode(self):
        """Batch geocode partners. If called on a recordset, geocodes those partners. 
        Otherwise, geocodes all partners without coordinates."""
        if self:
            partners = self
            _logger.info("Barikoi: Batch geocoding selected partners: %s", self.ids)
        else:
            partners = self.search([
                ('street', '!=', False),
                ('partner_latitude', '=', False),
            ])
            _logger.info("Barikoi: Batch geocoding all partners without coordinates. Found: %d", len(partners))
        
        if not partners:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Partners to Geocode'),
                    'message': _('Please select partners or ensure they have a street address and no coordinates.'),
                    'type': 'info',
                }
            }
        
        success_count = 0
        fail_count = 0
        
        for partner in partners:
            try:
                result = partner.action_geocode_address()
                if result.get('params', {}).get('type') == 'success':
                    success_count += 1
                else:
                    fail_count += 1
            except Exception:
                fail_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Batch Geocoding Complete'),
                'message': _('Success: %d, Failed: %d') % (success_count, fail_count),
                'type': 'info',
                'sticky': True,
            }
        }

    def action_find_nearby_partners(self):
        """Find partners within a certain distance"""
        self.ensure_one()
        
        if not self.partner_latitude or not self.partner_longitude:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Coordinates'),
                    'message': _('Please geocode this partner first.'),
                    'type': 'warning',
                }
            }
        
        # Get distance threshold from settings (default 10km)
        distance_threshold = float(
            self.env['ir.config_parameter'].sudo().get_param(
                'barikoi.nearby_distance_threshold', '10'
            )
        )
        
        nearby_partners = self._find_partners_within_distance(
            self.partner_latitude,
            self.partner_longitude,
            distance_threshold
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Nearby Partners'),
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('id', 'in', nearby_partners.ids)],
            'target': 'current',
        }

    def _find_partners_within_distance(self, lat, lng, max_distance_km):
        """
        Find partners within a certain distance using Haversine formula
        """
        # Rough approximation: 1 degree ~ 111km
        lat_delta = max_distance_km / 111.0
        lng_delta = max_distance_km / (111.0 * math.cos(math.radians(lat)))
        
        candidates = self.search([
            ('id', '!=', self.id),
            ('partner_latitude', '!=', False),
            ('partner_longitude', '!=', False),
            ('partner_latitude', '>=', lat - lat_delta),
            ('partner_latitude', '<=', lat + lat_delta),
            ('partner_longitude', '>=', lng - lng_delta),
            ('partner_longitude', '<=', lng + lng_delta),
        ])
        
        nearby = self.env['res.partner']
        
        for partner in candidates:
            distance = self._haversine_distance(
                lat, lng,
                partner.partner_latitude, partner.partner_longitude
            )
            if distance <= max_distance_km:
                nearby |= partner
        
        return nearby

    @staticmethod
    def _haversine_distance(lat1, lon1, lat2, lon2):
        """Calculate distance between two points using Haversine formula."""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)
        
        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) *
             math.sin(delta_lon / 2) ** 2)
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        
        return R * c

    def _update_coordinates_direct(self, vals):
        """
        Directly update partner coordinates using SQL to bypass base_geolocalize.
        This ensures coordinates are saved even when base_geolocalize would reset them.
        """
        self.ensure_one()
        
        _logger.info("Barikoi: _update_coordinates_direct called for partner %s with vals=%s", self.id, vals)
        
        # Build SQL update
        update_fields = []
        update_values = []
        
        field_mapping = {
            'partner_latitude': 'partner_latitude',
            'partner_longitude': 'partner_longitude',
            'geocoding_status': 'geocoding_status',
            'last_geocoding_date': 'last_geocoding_date',
            'barikoi_place_id': 'barikoi_place_id',
            'barikoi_ucode': 'barikoi_ucode',
        }
        
        for val_key, db_field in field_mapping.items():
            if val_key in vals:
                update_fields.append(f'{db_field} = %s')
                update_values.append(vals[val_key])
        
        if not update_fields:
            _logger.warning("Barikoi: No fields to update in _update_coordinates_direct")
            return True
        
        # Add write_date and write_uid
        update_fields.append('write_date = NOW()')
        update_fields.append('write_uid = %s')
        update_values.append(self.env.uid)
        
        # Add partner id for WHERE clause
        update_values.append(self.id)
        
        query = f"UPDATE res_partner SET {', '.join(update_fields)} WHERE id = %s"
        
        _logger.info("Barikoi: Executing SQL: %s with values %s", query, update_values)
        
        self.env.cr.execute(query, update_values)
        
        # Invalidate cache for this record's fields to refresh without triggering ORM setters
        # In Odoo 19, use invalidate_recordset or invalidate_cache on specific fields
        fields_to_invalidate = [fname for fname in field_mapping.keys() if fname in vals]
        if fields_to_invalidate:
            self.invalidate_recordset(fields_to_invalidate)
        
        _logger.info("Barikoi: Direct SQL update for partner %s completed successfully", self.id)
        
        return True

    def geo_localize(self):
        """
        Override Odoo's geo_localize to use Barikoi instead of OpenStreetMap.
        This is called by the standard 'Geolocate' button in partner form.
        """
        # Check if Barikoi is enabled
        if self.env['ir.config_parameter'].sudo().get_param('barikoi.enabled') == 'True':
            _logger.info("Barikoi: Using Barikoi for geolocalization instead of OpenStreetMap")
            
            for partner in self:
                # Build address string
                address_parts = []
                if partner.street:
                    address_parts.append(partner.street)
                if partner.street2:
                    address_parts.append(partner.street2)
                if partner.city:
                    address_parts.append(partner.city)
                if partner.zip:
                    address_parts.append(partner.zip)
                
                if not address_parts:
                    partner.geocoding_status = 'failed'
                    continue
                
                address = ', '.join(address_parts)
                
                try:
                    api = self.env['barikoi.api']
                    result = api.geocode(address)
                    
                    if result and 'place' in result and result['place']:
                        place = result['place']
                        partner.with_context(barikoi_geocoding=True).write({
                            'partner_latitude': place.get('latitude'),
                            'partner_longitude': place.get('longitude'),
                            'barikoi_place_id': str(place.get('id')) if place.get('id') else False,
                            'barikoi_ucode': place.get('uCode'),
                            'geocoding_status': 'geocoded',
                            'last_geocoding_date': fields.Datetime.now(),
                        })
                        _logger.info("Barikoi: Geolocalized partner %s to lat=%s, lng=%s",
                                    partner.id, place.get('latitude'), place.get('longitude'))
                    else:
                        partner.geocoding_status = 'failed'
                        _logger.warning("Barikoi: Could not geolocate partner %s", partner.id)
                except Exception as e:
                    _logger.error("Barikoi: Geolocalization error for partner %s: %s", partner.id, str(e))
                    partner.geocoding_status = 'failed'
            
            return True
        else:
            # Fall back to parent (OpenStreetMap) if Barikoi is not enabled
            _logger.info("Barikoi: Barikoi not enabled, falling back to OpenStreetMap")
            return super().geo_localize()

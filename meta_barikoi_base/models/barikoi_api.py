# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import requests
import json

from odoo import api, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BarikoiAPI(models.AbstractModel):
    """Barikoi API Service - Core API handler for all Barikoi operations"""
    _name = 'barikoi.api'
    _description = 'Barikoi API Service'

    # Barikoi API Base URL
    BARIKOI_BASE_URL = 'https://barikoi.xyz/v2/api'

    @api.model
    def _get_api_key(self):
        """Get the Barikoi API key from configuration"""
        return self.env['ir.config_parameter'].sudo().get_param('barikoi.api_key')

    @api.model
    def _is_enabled(self):
        """Check if Barikoi is enabled"""
        return self.env['ir.config_parameter'].sudo().get_param('barikoi.enabled') == 'True'

    @api.model
    def _is_default_provider(self):
        """Check if Barikoi is the default map provider"""
        return self.env['ir.config_parameter'].sudo().get_param('barikoi.default_provider') == 'True'

    def _make_request(self, endpoint, params=None, method='GET', timeout=30):
        """
        Make a request to Barikoi API
        
        Args:
            endpoint: API endpoint (e.g., '/search/autocomplete/place')
            params: Dictionary of query parameters
            method: HTTP method (GET or POST)
            
        Returns:
            dict: JSON response from the API
        """
        api_key = self._get_api_key()
        if not api_key:
            raise UserError(_('Barikoi API Key is not configured. Please configure it in Settings.'))
        
        url = f"{self.BARIKOI_BASE_URL}{endpoint}"
        
        # Add API key to params
        if params is None:
            params = {}
        params['api_key'] = api_key
        
        try:
            if method == 'GET':
                response = requests.get(url, params=params, timeout=timeout)
            else:
                response = requests.post(url, json=params, timeout=timeout)
            
            response.raise_for_status()
            return response.json()
        except requests.exceptions.Timeout:
            _logger.error("Barikoi API request timed out")
            raise UserError(_('Barikoi API request timed out. Please try again.'))
        except requests.exceptions.ConnectionError:
            _logger.error("Failed to connect to Barikoi API")
            raise UserError(_('Failed to connect to Barikoi API. Please check your internet connection.'))
        except requests.exceptions.HTTPError as e:
            _logger.error("Barikoi API HTTP error: %s", str(e))
            raise UserError(_('Barikoi API error: %s') % str(e))
        except json.JSONDecodeError:
            _logger.error("Invalid JSON response from Barikoi API")
            raise UserError(_('Invalid response from Barikoi API.'))
        except Exception as e:
            _logger.error("Barikoi API error: %s", str(e))
            raise UserError(_('Barikoi API error: %s') % str(e))

    @api.model
    def test_connection(self):
        """Test the API connection with a simple autocomplete request"""
        try:
            result = self.autocomplete('dhaka')
            if result and 'places' in result:
                return {'status': 'success', 'message': 'Connection successful'}
            elif result and 'status' in result and result['status'] == 200:
                return {'status': 'success', 'message': 'Connection successful'}
            else:
                return {'status': 'error', 'message': 'Invalid API response'}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}

    @api.model
    def autocomplete(self, query, city=None, sub_area=True, sub_district=True, limit=10):
        """
        Autocomplete place search
        
        Args:
            query: Search query string
            city: Optional city filter
            sub_area: Include sub_area in response
            sub_district: Include sub_district in response
            limit: Maximum number of results
            
        Returns:
            dict: Autocomplete results
        """
        params = {
            'q': query,
            'sub_area': str(sub_area).lower(),
            'sub_district': str(sub_district).lower(),
        }
        if city:
            params['city'] = city
        
        result = self._make_request('/search/autocomplete/place', params)
        
        # Log the raw API response for debugging
        _logger.info("Barikoi autocomplete response for query '%s': %s", query, result)
        
        return result

    @api.model
    def place_details(self, place_id):
        """
        Get details for a specific place
        
        Args:
            place_id: Barikoi place ID
            
        Returns:
            dict: Place details
        """
        params = {'id': place_id}
        return self._make_request('/place/details', params)

    @api.model
    def reverse_geocode(self, latitude, longitude, **options):
        """
        Reverse geocode coordinates to address
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            options: Additional options (district, post_code, country, sub_district, 
                    union, pauroshova, location_type, division, address, area, bangla)
            
        Returns:
            dict: Reverse geocoding result
        """
        params = {
            'longitude': longitude,
            'latitude': latitude,
            'district': options.get('district', True),
            'post_code': options.get('post_code', True),
            'country': options.get('country', True),
            'sub_district': options.get('sub_district', True),
            'union': options.get('union', True),
            'pauroshova': options.get('pauroshova', True),
            'location_type': options.get('location_type', True),
            'division': options.get('division', True),
            'address': options.get('address', True),
            'area': options.get('area', True),
            'bangla': options.get('bangla', False),
        }
        
        return self._make_request('/search/reverse/geocode', params, timeout=options.get('timeout', 30))

    @api.model
    def geocode(self, address, city=None):
        """
        Geocode address to coordinates using autocomplete API
        
        Args:
            address: Address string to geocode
            city: Optional city filter
            
        Returns:
            dict: Geocoding result with place containing latitude, longitude, and uCode
        """
        # Use autocomplete API since /search/geocode endpoint doesn't exist
        result = self.autocomplete(address, city=city, limit=1)
        
        _logger.info("Barikoi geocode raw result for '%s': %s", address, result)
        
        if result and 'places' in result and len(result['places']) > 0:
            place = result['places'][0]
            _logger.info("Barikoi geocode first place: %s", place)
            
            # Extract latitude and longitude - handle both string and float
            try:
                lat = place.get('latitude')
                lon = place.get('longitude')
                
                # Convert to float if string
                if isinstance(lat, str):
                    lat = float(lat) if lat else 0.0
                if isinstance(lon, str):
                    lon = float(lon) if lon else 0.0
                    
                _logger.info("Barikoi geocode parsed coordinates: lat=%s, lon=%s", lat, lon)
            except (ValueError, TypeError) as e:
                _logger.error("Barikoi geocode coordinate parsing error: %s", e)
                lat = 0.0
                lon = 0.0
            
            return {
                'place': {
                    'id': place.get('id'),
                    'latitude': lat,
                    'longitude': lon,
                    'address': place.get('address'),
                    'city': place.get('city'),
                    'area': place.get('area'),
                    'district': place.get('district'),
                    'post_code': place.get('postCode'),
                    'uCode': place.get('uCode'),
                    'division': place.get('division'),
                    'sub_district': place.get('sub_district'),
                    'thana': place.get('thana'),
                }
            }
        
        _logger.warning("Barikoi geocode: No places found for address '%s'", address)
        return {'place': None}

    @api.model
    def route(self, coordinates, geometries='polyline'):
        """
        Get route between coordinates
        
        Args:
            coordinates: Semicolon-separated coordinates (lon,lat;lon,lat)
            geometries: Geometry format (polyline or geojson)
            
        Returns:
            dict: Route information
        """
        params = {
            'geometries': geometries,
        }
        endpoint = f'/route/{coordinates}'
        return self._make_request(endpoint, params)

    @api.model
    def nearby(self, latitude, longitude, radius=1000, limit=10, place_type=None):
        """
        Find nearby places
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius: Search radius in meters
            limit: Maximum number of results
            place_type: Type of place to search for
            
        Returns:
            dict: Nearby places
        """
        params = {
            'latitude': latitude,
            'longitude': longitude,
            'radius': radius,
            'limit': limit,
        }
        if place_type:
            params['type'] = place_type
        
        return self._make_request('/search/nearby', params)

    @api.model
    def parse_address_components(self, barikoi_data):
        """
        Parse Barikoi address data into Odoo partner fields format
        
        Args:
            barikoi_data: Dictionary from Barikoi API response
            
        Returns:
            dict: Mapped fields for res.partner
        """
        result = {}
        
        # Street address
        if barikoi_data.get('address'):
            result['street'] = barikoi_data['address']
        
        # Area (often used as street2 in Bangladesh)
        if barikoi_data.get('area'):
            result['street2'] = barikoi_data['area']
        
        # City
        if barikoi_data.get('city'):
            result['city'] = barikoi_data['city']
        
        # ZIP/Post Code
        if barikoi_data.get('post_code'):
            result['zip'] = barikoi_data['post_code']
        
        # Coordinates
        if barikoi_data.get('latitude'):
            result['partner_latitude'] = float(barikoi_data['latitude'])
        if barikoi_data.get('longitude'):
            result['partner_longitude'] = float(barikoi_data['longitude'])
        
        # Bangladesh-specific fields
        if barikoi_data.get('division'):
            result['barikoi_division'] = barikoi_data['division']
        if barikoi_data.get('district'):
            result['barikoi_district'] = barikoi_data['district']
        if barikoi_data.get('sub_district'):
            result['barikoi_upazila'] = barikoi_data['sub_district']
        if barikoi_data.get('union'):
            result['barikoi_union'] = barikoi_data['union']
        
        return result
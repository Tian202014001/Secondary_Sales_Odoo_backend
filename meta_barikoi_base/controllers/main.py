# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import json

from odoo import http
from odoo.http import request, Response
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BarikoiController(http.Controller):
    """Main controller for Barikoi API endpoints"""

    @http.route('/barikoi/autocomplete', type='http', auth='user', methods=['GET'], csrf=False)
    def autocomplete(self, q, city=None, **kwargs):
        """
        Autocomplete endpoint for address search
        
        Args:
            q: Search query
            city: Optional city filter
            
        Returns:
            JSON response with autocomplete results
        """
        try:
            api = request.env['barikoi.api']
            result = api.autocomplete(q, city=city)
            return Response(
                json.dumps(result),
                content_type='application/json',
                status=200
            )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi autocomplete error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error'}),
                content_type='application/json',
                status=500
            )

    @http.route('/barikoi/place/details', type='http', auth='user', methods=['GET'], csrf=False)
    def place_details(self, id, **kwargs):
        """
        Get place details by ID
        
        Args:
            id: Barikoi place ID
            
        Returns:
            JSON response with place details
        """
        try:
            api = request.env['barikoi.api']
            result = api.place_details(id)
            return Response(
                json.dumps(result),
                content_type='application/json',
                status=200
            )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi place details error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error'}),
                content_type='application/json',
                status=500
            )

    @http.route('/barikoi/reverse_geocode', type='http', auth='user', methods=['GET'], csrf=False)
    def reverse_geocode(self, latitude, longitude, **kwargs):
        """
        Reverse geocode coordinates to address
        
        Args:
            latitude: Latitude coordinate
            longitude: Longitude coordinate
            
        Returns:
            JSON response with address information
        """
        try:
            api = request.env['barikoi.api']
            result = api.reverse_geocode(latitude, longitude, **kwargs)
            return Response(
                json.dumps(result),
                content_type='application/json',
                status=200
            )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi reverse geocode error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error'}),
                content_type='application/json',
                status=500
            )

    @http.route('/barikoi/geocode', type='http', auth='user', methods=['GET'], csrf=False)
    def geocode(self, q, city=None, **kwargs):
        """
        Geocode address to coordinates
        
        Args:
            q: Address query
            city: Optional city filter
            
        Returns:
            JSON response with coordinates
        """
        try:
            api = request.env['barikoi.api']
            result = api.geocode(q, city=city)
            return Response(
                json.dumps(result),
                content_type='application/json',
                status=200
            )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi geocode error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error'}),
                content_type='application/json',
                status=500
            )

    @http.route('/barikoi/route', type='http', auth='user', methods=['GET'], csrf=False)
    def route(self, coordinates, geometries='polyline', **kwargs):
        """
        Get route between coordinates
        
        Args:
            coordinates: Semicolon-separated coordinates (lon,lat;lon,lat)
            geometries: Geometry format (polyline or geojson)
            
        Returns:
            JSON response with route information
        """
        try:
            api = request.env['barikoi.api']
            result = api.route(coordinates, geometries=geometries)
            return Response(
                json.dumps(result),
                content_type='application/json',
                status=200
            )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi route error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error'}),
                content_type='application/json',
                status=500
            )

    @http.route('/barikoi/nearby', type='http', auth='user', methods=['GET'], csrf=False)
    def nearby(self, latitude, longitude, radius=1000, limit=10, place_type=None, **kwargs):
        """
        Find nearby places
        
        Args:
            latitude: Center latitude
            longitude: Center longitude
            radius: Search radius in meters
            limit: Maximum number of results
            place_type: Type of place to search for
            
        Returns:
            JSON response with nearby places
        """
        try:
            api = request.env['barikoi.api']
            result = api.nearby(
                latitude, longitude,
                radius=int(radius),
                limit=int(limit),
                place_type=place_type
            )
            return Response(
                json.dumps(result),
                content_type='application/json',
                status=200
            )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e)}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi nearby error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error'}),
                content_type='application/json',
                status=500
            )

    @http.route('/barikoi/config', type='http', auth='user', methods=['GET'], csrf=False)
    def get_config(self, **kwargs):
        """
        Get Barikoi configuration status
        
        Returns:
            JSON response with configuration status
        """
        try:
            enabled = request.env['ir.config_parameter'].sudo().get_param('barikoi.enabled')
            default_provider = request.env['ir.config_parameter'].sudo().get_param('barikoi.default_provider')
            has_api_key = bool(request.env['ir.config_parameter'].sudo().get_param('barikoi.api_key'))
            
            return Response(
                json.dumps({
                    'enabled': enabled == 'True',
                    'default_provider': default_provider == 'True',
                    'has_api_key': has_api_key,
                }),
                content_type='application/json',
                status=200
            )
        except Exception as e:
            _logger.error("Barikoi config error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error'}),
                content_type='application/json',
                status=500
            )
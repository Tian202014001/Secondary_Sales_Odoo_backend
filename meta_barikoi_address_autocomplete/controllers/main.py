# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
import json

from odoo import http
from odoo.http import request, Response
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class BarikoiAddressAutocompleteController(http.Controller):
    """Controller for Barikoi address autocomplete endpoints"""

    @http.route('/barikoi/address/autocomplete', type='http', auth='user', methods=['GET'], csrf=False)
    def address_autocomplete(self, q, city=None, **kwargs):
        """
        Address autocomplete endpoint for partner forms
        
        Args:
            q: Search query
            city: Optional city filter
            
        Returns:
            JSON response with autocomplete results formatted for Odoo fields
        """
        try:
            api = request.env['barikoi.api']
            result = api.autocomplete(q, city=city)
            
            # Format results for frontend consumption
            places = []
            if result and 'places' in result:
                for place in result['places']:
                    places.append({
                        'id': place.get('id'),
                        'name': place.get('name', ''),
                        'address': place.get('address', ''),
                        'area': place.get('area', ''),
                        'city': place.get('city', ''),
                        'post_code': place.get('post_code', ''),
                        'latitude': place.get('latitude'),
                        'longitude': place.get('longitude'),
                        'division': place.get('division', ''),
                        'district': place.get('district', ''),
                        'sub_district': place.get('sub_district', ''),
                        'union': place.get('union', ''),
                        'label': self._format_place_label(place),
                    })
            
            return Response(
                json.dumps({'places': places, 'status': 200}),
                content_type='application/json',
                status=200
            )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e), 'places': [], 'status': 400}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi address autocomplete error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error', 'places': [], 'status': 500}),
                content_type='application/json',
                status=500
            )

    @http.route('/barikoi/address/details', type='http', auth='user', methods=['GET'], csrf=False)
    def address_details(self, id, **kwargs):
        """
        Get full address details for a selected place
        
        Args:
            id: Barikoi place ID
            
        Returns:
            JSON response with full address details mapped to Odoo fields
        """
        try:
            api = request.env['barikoi.api']
            result = api.place_details(id)
            
            if result and 'place' in result:
                place = result['place']
                # Parse address components for Odoo fields
                address_data = api.parse_address_components(place)
                address_data['barikoi_place_id'] = place.get('id')
                address_data['place_name'] = place.get('name', '')
                
                # Add additional fields for frontend
                address_data['postcode'] = place.get('post_code', '')
                address_data['thana'] = place.get('sub_district', '')
                address_data['area'] = place.get('area', '')
                address_data['sector'] = place.get('sector', '')
                address_data['road'] = place.get('road', '')
                address_data['division'] = place.get('division', '')
                address_data['district'] = place.get('district', '')
                address_data['post_office'] = place.get('post_office', '')
                address_data['latitude'] = place.get('latitude', '')
                address_data['longitude'] = place.get('longitude', '')
                
                # Get Bangladesh country ID
                bangladesh = request.env['res.country'].sudo().search([('code', '=', 'BD')], limit=1)
                if bangladesh:
                    address_data['country_id'] = bangladesh.id
                
                # Try to find matching state (division/district)
                state_name = place.get('division') or place.get('district')
                if state_name:
                    state = request.env['res.country.state'].sudo().search([
                        '|', '|',
                        ('name', '=ilike', state_name),
                        ('name', '=ilike', state_name + '%'),
                        ('name', '=ilike', '%' + state_name),
                        ('country_id.code', '=', 'BD')
                    ], limit=1)
                    if state:
                        address_data['state_id'] = state.id
                
                return Response(
                    json.dumps({'address': address_data, 'status': 200}),
                    content_type='application/json',
                    status=200
                )
            else:
                return Response(
                    json.dumps({'error': 'Place not found', 'status': 404}),
                    content_type='application/json',
                    status=404
                )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e), 'status': 400}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi address details error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error', 'status': 500}),
                content_type='application/json',
                status=500
            )

    @http.route('/barikoi/address/partner/<int:partner_id>/update', type='http', auth='user', methods=['POST'], csrf=False)
    def update_partner_address(self, partner_id, **kwargs):
        """
        Update partner address from Barikoi place data
        
        Args:
            partner_id: Partner record ID
            
        POST data:
            place_id: Barikoi place ID
            
        Returns:
            JSON response with update status
        """
        try:
            partner = request.env['res.partner'].browse(partner_id)
            if not partner.exists():
                return Response(
                    json.dumps({'error': 'Partner not found', 'status': 404}),
                    content_type='application/json',
                    status=404
                )
            
            place_id = kwargs.get('place_id') or request.httprequest.form.get('place_id')
            if not place_id:
                return Response(
                    json.dumps({'error': 'Place ID required', 'status': 400}),
                    content_type='application/json',
                    status=400
                )
            
            # Get place details and update partner
            api = request.env['barikoi.api']
            result = api.place_details(place_id)
            
            if result and 'place' in result:
                partner.update_from_barikoi_place(result['place'])
                return Response(
                    json.dumps({'status': 'success', 'message': 'Address updated', 'status_code': 200}),
                    content_type='application/json',
                    status=200
                )
            else:
                return Response(
                    json.dumps({'error': 'Place not found', 'status': 404}),
                    content_type='application/json',
                    status=404
                )
        except UserError as e:
            return Response(
                json.dumps({'error': str(e), 'status': 400}),
                content_type='application/json',
                status=400
            )
        except Exception as e:
            _logger.error("Barikoi partner update error: %s", str(e))
            return Response(
                json.dumps({'error': 'Internal server error', 'status': 500}),
                content_type='application/json',
                status=500
            )

    def _format_place_label(self, place):
        """Format a place for display in autocomplete dropdown"""
        parts = []
        
        if place.get('name'):
            parts.append(place['name'])
        if place.get('address') and place.get('address') != place.get('name'):
            parts.append(place['address'])
        if place.get('area'):
            parts.append(place['area'])
        if place.get('city'):
            parts.append(place['city'])
        
        return ', '.join(parts)
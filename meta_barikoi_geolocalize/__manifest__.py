# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Meta Barikoi Geolocalize",
    'version': '18.0.1.0.0',
    'summary': 'Partner geolocalization using Barikoi API for Bangladesh',
    'description': """
Partner Geolocalization using Barikoi API for Bangladesh

This module provides geolocalization functionality using Barikoi API.

Features:
---------
🎯 Geocoding Status Tracking
   - Visual badge showing geocoding state (Not Geocoded/Geocoded/Failed)
   - Auto-updates when coordinates are set or cleared
   - Color-coded: Yellow (pending), Green (success), Red (failed)
   - Last geocoding date tracking

📍 Geocoding Operations
   - Manual geocoding from partner form
   - Reverse geocoding (coordinates to address)
   - Batch geocoding for multiple partners

👥 Nearby Partner Search
   - Find partners within configurable distance
   - Uses Haversine formula for accuracy
   - Default 10km radius (configurable)

🔧 Technical Fields Added:
   - geocoding_status: Selection field with badge widget
   - last_geocoding_date: Datetime field
   - has_valid_coordinates: Computed boolean

Maintainer: nsrshishir
Company: Metamorphosis Ltd.
    """,
    'category': 'Tools',
    'author': 'Metamorphosis Ltd.',
    'maintainer': 'nsrshishir',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'web',
        'contacts',
        'base_geolocalize',
        'meta_barikoi_base',
        'meta_barikoi_address_autocomplete',
    ],
    'data': [
        'views/res_partner_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [
        'demo/res_partner_demo.xml',
    ],
    'installable': True,
    'application': False,
}
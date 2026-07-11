# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Meta Barikoi Partner Map",
    'version': '18.0.1.0.0',
    'summary': 'Interactive map display for partner locations using Barikoi',
    'description': """
Partner Map Display using Barikoi API
======================================

This module provides interactive map display for partner locations.

Features:
---------
🗺️ Interactive Map Widget
   - Display partner location on Barikoi map
   - Click to set location
   - Drag marker to update coordinates
   - Auto-center on partner coordinates

📍 Map View in Partner Form
   - Shows map in partner form sidebar
   - Updates coordinates when marker is dragged
   - Shows partner name on marker popup

👥 Partner Map View (List View)
   - See all partners on a single map
   - Filter partners by location
   - Click marker to open partner form

🔧 Technical Details:
   - Widget: barikoi_partner_map
   - Uses Barikoi Map SDK
   - OWL Component: PartnerMap

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
        'meta_barikoi_base',
        'meta_barikoi_geolocalize',
    ],
    'data': [
        'views/res_partner_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # Native map widget removed - now redirects to Barikoi web map
        ],
    },
    'installable': True,
    'application': False,
}
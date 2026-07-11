# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Meta Barikoi Address Autocomplete",
    'version': '18.0.1.0.0',
    'summary': 'Address autocomplete using Barikoi API for Bangladesh',
    'description': """
Address Autocomplete using Barikoi API for Bangladesh

This module provides address autocomplete functionality using Barikoi API.
It integrates with partner forms for seamless address entry.

Features:
---------
🔍 Address Autocomplete Widget
   - Real-time suggestions as you type (min 2 characters)
   - Keyboard navigation (Arrow keys, Enter, Escape)
   - Dropdown with address previews
   - Debounced API calls (300ms)

📍 Automatic Field Population
   When selecting an address, automatically fills:
   - Street (full address)
   - Street2 (area)
   - City
   - ZIP/Postcode
   - State (matched to Bangladesh states)
   - Country (set to Bangladesh)
   - Coordinates (latitude/longitude)

🇧🇩 Bangladesh-Specific Fields
   - barikoi_division: Administrative Division
   - barikoi_district: District
   - barikoi_upazila: Upazila/Sub-District
   - barikoi_union: Union
   - barikoi_place_id: Barikoi reference ID

🔧 Technical Details:
   - Widget: barikoi_autocomplete
   - Field Type: char
   - OWL Component: BarikoiAutocomplete

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
        'meta_barikoi_base',
    ],
    'data': [
        'views/res_partner_views.xml',
        'views/res_company_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'meta_barikoi_address_autocomplete/static/src/js/barikoi_autocomplete.js',
            'meta_barikoi_address_autocomplete/static/src/scss/barikoi_autocomplete.scss',
            'meta_barikoi_address_autocomplete/static/src/xml/barikoi_autocomplete.xml',
        ],
    },
    'installable': True,
    'application': False,
}
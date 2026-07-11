# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Meta Barikoi Maps Base",
    'version': '18.0.1.0.1',
    'summary': 'Base module for Barikoi Maps integration in Odoo',
    'description': """
This module provides the core functionality for Barikoi Maps integration.
It includes API configuration, base services, and utility functions.

Features:
- Barikoi API key configuration in settings
- Base API service for all Barikoi API calls
- Geocoding and reverse geocoding support
- Bangladesh-specific address field handling

Maintainer: nsrshishir
Company: Metamorphosis Ltd.
    """,
    'category': 'Tools',
    'author': 'Metamorphosis Ltd.',
    'maintainer': 'nsrshishir',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'base_setup',
        'web',
    ],
    'data': [
        'views/res_config_settings_views.xml',
        'views/barikoi_menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'meta_barikoi_base/static/src/js/barikoi_service.js',
        ],
    },
    'installable': True,
    'application': False,
}

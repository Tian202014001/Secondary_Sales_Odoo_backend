# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': "Barikoi Maps for Odoo",
    'version': '18.0.1.0.0',
    'summary': 'Complete Barikoi Maps integration for Bangladesh addresses',
    'description': """
Barikoi Maps Integration for Odoo 18
====================================

This is the main application module that provides complete Barikoi Maps 
integration for Odoo, similar to Google Maps functionality but specifically 
designed for Bangladesh.

Features:
---------
- Address autocomplete using Barikoi API
- Partner geolocalization with map display
- Website map integration with MapLibre GL JS
- Bangladesh-specific address fields (Division, District, Upazila, Union)
- Batch geocoding for existing partners
- Reverse geocoding support

Auto-installed Dependencies:
----------------------------
When you install this module, it automatically installs:
- meta_barikoi_base: Core API configuration and services
- meta_barikoi_address_autocomplete: Address autocomplete widget
- meta_barikoi_geolocalize: Partner geolocalization
- base_geolocalize: Odoo's base geolocalization support

Configuration:
--------------
1. Go to Website → Configuration → Barikoi Settings
2. Enter your Barikoi API key (get one from https://docs.barikoi.com/)
3. Click "Test Connection" to verify

Maintainer: nsrshishir
Company: Metamorphosis Ltd.
    """,
    'category': 'Website',
    'author': 'Metamorphosis Ltd.',
    'maintainer': 'nsrshishir',
    'license': 'LGPL-3',
    'depends': [
        'base_geolocalize',
        'meta_barikoi_base',
        'meta_barikoi_address_autocomplete',
        'meta_barikoi_geolocalize',
    ],
    'data': [
        'views/barikoi_settings_views.xml',
    ],
    'assets': {
    },
    'installable': True,
    'application': True,
    'auto_install': True,
}
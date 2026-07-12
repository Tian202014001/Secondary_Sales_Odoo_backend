# -*- coding: utf-8 -*-
{
    "name": "Secondary Sales - Location Tracking",
    "summary": "Real-time employee GPS tracking, attendance-linked path history, and Leaflet.js dashboard.",
    "description": """
        This module provides model storage, APIs, and dashboard maps for tracking
        sales employee coordinates during active attendance shifts.
    """,
    "author": "Antigravity",
    "category": "Sales/Secondary Sales",
    "version": "18.0.1.0.0",
    "depends": [
        "base",
        "hr",
        "hr_attendance",
        "meta_api_user",
        "meta_ss_rest_api",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/res_config_settings_views.xml",
        "views/sales_employee_location_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css",
            "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js",
            "meta_ss_location_tracking/static/src/components/route_map/route_map.xml",
            "meta_ss_location_tracking/static/src/components/route_map/route_map.scss",
            "meta_ss_location_tracking/static/src/components/route_map/route_map.js",
            # Barikoi GL JS
            "meta_ss_location_tracking/static/src/components/barikoi_route_map/barikoi_route_map.xml",
            "meta_ss_location_tracking/static/src/components/barikoi_route_map/barikoi_route_map.scss",
            "meta_ss_location_tracking/static/src/components/barikoi_route_map/barikoi_route_map.js",
        ],
    },
    "installable": True,
    "application": False,
    "license": "LGPL-3",
}

# -*- coding: utf-8 -*-

{
    "name": "Meta API User",
    "version": "18.0.0.1.0",
    "summary": "Mobile API users with JWT access tokens and refresh sessions",
    "description": """
        Foundation module for mobile API authentication using custom mobile
        users, bcrypt password hashes, JWT access tokens, and revocable
        opaque refresh-token sessions.
    """,
    "category": "Technical",
    "author": "Meta",
    "license": "LGPL-3",
    "depends": ["base", "base_setup", "hr", "web"],
    "data": [
        "security/meta_api_user_security.xml",
        "security/ir.model.access.csv",
        "data/mobile_permission_cleanup.xml",
        "views/ss_module_views.xml",
        "views/mobile_role_views.xml",
        "views/mobile_ui_resource_views.xml",
        "views/res_mobile_user_views.xml",
        "views/mobile_auth_session_views.xml",
        "views/res_config_settings_views.xml",
        "views/mobile_auth_dashboard_views.xml",
        "views/menu_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "meta_api_user/static/src/components/mobile_auth_dashboard/mobile_auth_dashboard.xml",
            "meta_api_user/static/src/components/mobile_auth_dashboard/mobile_auth_dashboard.scss",
            "meta_api_user/static/src/components/mobile_auth_dashboard/mobile_auth_dashboard.js",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}

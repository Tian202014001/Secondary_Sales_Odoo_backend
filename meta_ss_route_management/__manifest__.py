# -*- coding: utf-8 -*-
{
    "name": "Meta SS Route Management",
    "version": "18.0.0.1.0",
    "summary": "Route Management for secondary sales app",
    "description": """
        Provides route planning and management features for the sales team.
    """,
    "category": "Sales",
    "author": "Abrar Ahmed Tian",
    "license": "LGPL-3",
    "depends": ["meta_ss_rest_api", "base", "hr", "meta_ss_contact", "meta_api_user"],
    "data": [
        "security/ir.model.access.csv",
        "views/route_management_views.xml",
        "views/route_planner_views.xml",
        "views/outlet_visit_views.xml",
        "views/res_partner.xml",
        "views/hr_employee.xml",
    ],
    "installable": True,
    "application": True,
    "auto_install": False,
}

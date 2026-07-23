# -*- coding: utf-8 -*-
{
    "name": "Meta SS Transfer",
    "version": "18.0.0.1.0",
    "summary": "Virtual location transfers for secondary sales",
    "description": """
        Adds a Virtual Location Transfer operation type to move stock between
        distributor and sales officer virtual locations.
    """,
    "category": "Inventory",
    "author": "Abrar Ahmed Tian",
    "license": "LGPL-3",
    "depends": ["meta_ss_rest_api", "stock", "meta_ss_contact", "hr"],
    "data": [
        "data/stock_location_data.xml",
        "data/stock_picking_type_data.xml",
        "views/stock_picking_views.xml",
        "views/stock_location_views.xml",
        "views/res_partner_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

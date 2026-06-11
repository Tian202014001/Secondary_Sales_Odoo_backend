# -*- coding: utf-8 -*-
{
    "name": "Meta SS Sales",
    "version": "18.0.0.1.0",
    "summary": "Custom fields and views for Sales for secondary sales app",
    "description": """
        Extends sales orders (sale.order) with custom fields such as Sale Type
        and adds them to the order form view.
    """,
    "category": "Sales",
    "author": "Meta",
    "license": "LGPL-3",
    "depends": ["sale_stock", "meta_ss_contact", "meta_ss_route_management"],
    "data": [
        "views/sale_order_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

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
    "depends": ["meta_ss_rest_api", "sale_stock", "meta_ss_contact", "meta_ss_route_management", "meta_ss_transfer"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_sequence_data.xml",
        "views/sale_order_views.xml",
        "views/sale_target_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

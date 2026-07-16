# -*- coding: utf-8 -*-
{
    "name": "Meta SS Contact",
    "version": "18.0.0.1.0",
    "summary": "Custom fields and views for Contacts for secondary sales app",
    "description": """
        Extends contacts (res.partner) with custom fields such as Customer Type
        and adds them to the partner form view.
    """,
    "category": "Contacts",
    "author": "Meta",
    "license": "LGPL-3",
    "depends": ["meta_ss_rest_api", "base", "stock", "contacts"],
    "data": [
        "security/ir.model.access.csv",
        "wizard/create_van_location_wizard_views.xml",
        "views/res_contact.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}

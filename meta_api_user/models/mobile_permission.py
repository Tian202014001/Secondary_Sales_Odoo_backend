# -*- coding: utf-8 -*-

from odoo import fields, models


class ResMobilePermission(models.Model):
    _name = "res.mobile.permission"
    _description = "Mobile App Permission"
    _order = "category, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True, help="Unique string identifier checked by Flutter/APIs (e.g., 'dealer.create')")
    category = fields.Char(string="Category", default="General")
    active = fields.Boolean(default=True)
    description = fields.Text()

    _sql_constraints = [
        ("code_unique", "unique(code)", "The permission code must be unique."),
    ]

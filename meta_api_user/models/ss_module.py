# -*- coding: utf-8 -*-

from odoo import fields, models


class SsModule(models.Model):
    _name = "ss.module"
    _description = "Mobile Security Module"
    _order = "sequence, name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    sequence = fields.Integer(default=10)
    resource_ids = fields.Many2many(
        "mobile.ui.resource",
        "ss_module_resource_rel",
        "module_id",
        "resource_id",
        string="Resources",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        ("code_uniq", "unique(code)", "The module code must be unique."),
    ]

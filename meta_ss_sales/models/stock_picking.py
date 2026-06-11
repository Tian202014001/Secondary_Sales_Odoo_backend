# -*- coding: utf-8 -*-

from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    so_employee_id = fields.Many2one(
        "hr.employee",
        string="Sales Employee",
        related="sale_id.so_employee_id",
        store=True,
        index=True,
        readonly=True,
        help="Sales employee from the source sale order.",
    )

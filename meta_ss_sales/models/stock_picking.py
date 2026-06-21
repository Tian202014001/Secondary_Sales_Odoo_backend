# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    so_employee_id = fields.Many2one(
        "hr.employee",
        string="Sales Employee",
        compute="_compute_so_employee_id",
        store=True,
        readonly=False,
        index=True,
        help="Sales employee from the source sale order or assigned directly.",
    )

    @api.depends("sale_id.so_employee_id")
    def _compute_so_employee_id(self):
        for picking in self:
            if picking.sale_id and picking.sale_id.so_employee_id:
                picking.so_employee_id = picking.sale_id.so_employee_id
            else:
                picking.so_employee_id = picking.so_employee_id

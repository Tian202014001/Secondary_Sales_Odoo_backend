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

    ss_picking_type = fields.Selection(
        [("primary", "Primary"), ("secondary", "Secondary")],
        string="SS Picking Type",
        compute="_compute_ss_picking_type",
        store=True,
        readonly=False,
        default="primary",
        index=True,
    )

    van_operation_type = fields.Selection(
        [("load", "Load"), ("unload", "Unload")],
        string="Van Operation Type",
        help="Defines if this is a van load or unload operation.",
    )

    @api.depends("sale_id.so_employee_id")
    def _compute_so_employee_id(self):
        for picking in self:
            if picking.sale_id and picking.sale_id.so_employee_id:
                picking.so_employee_id = picking.sale_id.so_employee_id
            else:
                picking.so_employee_id = picking.so_employee_id or False

    @api.depends("sale_id.sale_type")
    def _compute_ss_picking_type(self):
        for picking in self:
            if picking.sale_id and picking.sale_id.sale_type:
                picking.ss_picking_type = picking.sale_id.sale_type
            else:
                picking.ss_picking_type = picking.ss_picking_type or "primary"

# -*- coding: utf-8 -*-

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    ss_scrap_qty = fields.Float(
        string="Scrap Qty",
        default=0.0,
        digits="Product Unit of Measure",
    )
    so_qty = fields.Float(
        string="SO Qty",
        default=0.0,
        digits="Product Unit of Measure",
    )
    qc_qty = fields.Float(
        string="QC Qty",
        default=0.0,
        digits="Product Unit of Measure",
    )


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    ss_scrap_qty = fields.Float(
        string="Scrap Qty",
        default=0.0,
        digits="Product Unit of Measure",
    )
    so_qty = fields.Float(
        string="SO Qty",
        default=0.0,
        digits="Product Unit of Measure",
    )
    qc_qty = fields.Float(
        string="QC Qty",
        default=0.0,
        digits="Product Unit of Measure",
    )

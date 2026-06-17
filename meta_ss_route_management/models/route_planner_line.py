# -*- coding: utf-8 -*-

from odoo import api, fields, models

class RoutePlannerLine(models.Model):
    _name = "route.planner.line"
    _description = "Route Planner Line"
    _order = "sequence, id"

    _sql_constraints = [
        (
            'day_of_week_uniq',
            'unique (planner_id, day_of_week)',
            'Each day of the week can only be added once per route plan.'
        )
    ]

    sequence = fields.Integer(string="Sequence", default=10)
    planner_id = fields.Many2one(
        'route.planner',
        string="Route Planner",
        required=True,
        ondelete='cascade',
    )
    day_of_week = fields.Selection(
        [
            ('0', 'Monday'),
            ('1', 'Tuesday'),
            ('2', 'Wednesday'),
            ('3', 'Thursday'),
            ('4', 'Friday'),
            ('5', 'Saturday'),
            ('6', 'Sunday'),
        ],
        string="Day of Week",
        required=True,
    )
    route_ids = fields.Many2many(
        'sale.route',
        'route_planner_line_sale_route_rel',
        'planner_line_id',
        'route_id',
        string="Routes",
        domain="[('active', '=', True)]"
    )

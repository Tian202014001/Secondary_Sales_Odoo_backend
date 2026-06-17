# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class RoutePlanner(models.Model):
    _name = "route.planner"
    _description = "Route Planner"
    _order = "id desc"

    name = fields.Char(
        string="Name",
        required=True,
    )
    distributor_id = fields.Many2one(
        'res.partner',
        string="Distributor",
        domain="[('customer_type', '=', 'distributor')]",
        required=True,
        help="Distributor for which this route plan is made.",
    )
    plan_line_ids = fields.One2many(
        'route.planner.line',
        'planner_id',
        string="Plan Lines",
    )
    active = fields.Boolean(default=True)


    @api.constrains('plan_line_ids')
    def _check_unique_days(self):
        for planner in self:
            days = [line.day_of_week for line in planner.plan_line_ids if line.day_of_week]
            if len(days) != len(set(days)):
                raise ValidationError(_("Each day of the week can only be added once per route plan."))

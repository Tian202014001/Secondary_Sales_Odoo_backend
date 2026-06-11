# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SSRouteVisitPlanLine(models.Model):
    _name = "sale.route.visit.plan.line"
    _description = "Route Visit Plan Line"
    _order = "plan_id, sequence, id"

    _sql_constraints = [
        ("plan_outlet_unique", "unique(plan_id, outlet_id)", "An outlet can only appear once in the same visit plan."),
    ]

    plan_id = fields.Many2one(
        "sale.route.visit.plan",
        string="Visit Plan",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    outlet_id = fields.Many2one(
        "res.partner",
        string="Outlet",
        required=True,
        domain="[('customer_type', '=', 'outlet')]",
    )
    expected_visit_time = fields.Float(string="Expected Visit Time")
    state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("visited", "Visited"),
            ("skipped", "Skipped"),
        ],
        default="pending",
        required=True,
    )
    note = fields.Char()

    @api.constrains("outlet_id")
    def _check_outlet_id(self):
        for line in self:
            if line.outlet_id and line.outlet_id.customer_type != "outlet":
                raise ValidationError(_("Visit plan outlet must be an outlet contact."))

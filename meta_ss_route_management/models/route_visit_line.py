# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SSRouteVisitLine(models.Model):
    _name = "sale.route.visit.line"
    _description = "Route Visit Line"
    _order = "visit_id, sequence, id"

    _sql_constraints = [
        ("visit_outlet_unique", "unique(visit_id, outlet_id)", "An outlet can only appear once in the same route visit."),
    ]

    visit_id = fields.Many2one(
        "sale.route.visit",
        string="Route Visit",
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
            ("checked_in", "Checked-In"),
            ("checked_out", "Checked-Out"),
            ("skipped", "Skipped"),
        ],
        default="checked_in",
        required=True,
    )
    note = fields.Char()
    check_in_time = fields.Datetime(string="Check-in Time", readonly=True)
    check_in_latitude = fields.Float(string="Check-in Latitude", digits=(10, 7), readonly=True)
    check_in_longitude = fields.Float(string="Check-in Longitude", digits=(10, 7), readonly=True)
    check_out_time = fields.Datetime(string="Check-out Time", readonly=True)
    check_out_latitude = fields.Float(string="Check-out Latitude", digits=(10, 7), readonly=True)
    check_out_longitude = fields.Float(string="Check-out Longitude", digits=(10, 7), readonly=True)

    @api.constrains("outlet_id")
    def _check_outlet_id(self):
        for line in self:
            if line.outlet_id and line.outlet_id.customer_type != "outlet":
                raise ValidationError(_("Route visit outlet must be an outlet contact."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._ensure_route_lines()
        return lines

    def write(self, vals):
        result = super().write(vals)
        if {"visit_id", "outlet_id", "sequence", "expected_visit_time"} & set(vals):
            self._ensure_route_lines()
        return result

    def _ensure_route_lines(self):
        route_line_model = self.env["sale.route.line"]
        for line in self:
            route = line.visit_id.route_id
            outlet = line.outlet_id
            if not route or not outlet:
                continue
            existing_route = outlet.outlet_route_id
            if existing_route and existing_route != route:
                raise ValidationError(
                    _("Outlet %(outlet)s is already assigned to route %(route)s.")
                    % {
                        "outlet": outlet.display_name,
                        "route": existing_route.display_name,
                    }
                )
            route_line = route_line_model.search([
                ("route_id", "=", route.id),
                ("outlet_id", "=", outlet.id),
            ], limit=1)
            if route_line:
                if not route_line.active:
                    route_line.active = True
                continue
            route_line_model.create({
                "route_id": route.id,
                "outlet_id": outlet.id,
                "sequence": line.sequence,
                "expected_visit_time": line.expected_visit_time,
            })

    def action_check_in(self):
        self.write({
            "state": "checked_in",
            "check_in_time": fields.Datetime.now(),
        })

    def action_check_out(self):
        for line in self:
            if line.state != "checked_in":
                raise ValidationError(_("You must check-in before checking out."))
        self.write({
            "state": "checked_out",
            "check_out_time": fields.Datetime.now(),
        })

    def action_mark_skipped(self):
        self.write({"state": "skipped"})

# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SSRouteVisitPlan(models.Model):
    _name = "sale.route.visit.plan"
    _description = "Route Visit Plan"
    _order = "visit_date desc, employee_id, route_id"

    _sql_constraints = [
        (
            "employee_route_date_unique",
            "unique(employee_id, route_id, visit_date)",
            "A visit plan already exists for this employee, route, and date.",
        ),
    ]

    name = fields.Char(compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Sales Employee",
        required=True,
    )
    route_id = fields.Many2one(
        "sale.route",
        string="Route",
        required=True,
        domain="[('active', '=', True)]",
    )
    distributor_contact_id = fields.Many2one(
        "res.partner",
        string="Distributor Contact",
        related="route_id.distributor_contact_id",
        store=True,
        readonly=True,
    )
    visit_date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("in_progress", "In Progress"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    plan_line_ids = fields.One2many(
        "sale.route.visit.plan.line",
        "plan_id",
        string="Planned Outlets",
    )

    @api.depends("employee_id", "route_id", "visit_date")
    def _compute_name(self):
        for plan in self:
            parts = [value for value in [
                plan.employee_id.name,
                plan.route_id.name,
                plan.visit_date and fields.Date.to_string(plan.visit_date),
            ] if value]
            plan.name = " / ".join(parts) or _("New Visit Plan")

    @api.onchange("route_id")
    def _onchange_route_id(self):
        if not self.route_id:
            return
        if len(self.route_id.ss_employee_ids) == 1 and not self.employee_id:
            self.employee_id = self.route_id.ss_employee_ids.id
        self.plan_line_ids = self._prepare_plan_line_commands(self.route_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("route_id") and not vals.get("plan_line_ids"):
                route = self.env["sale.route"].browse(vals["route_id"])
                vals["plan_line_ids"] = self._prepare_plan_line_commands(route, clear=False)
            if vals.get("route_id") and not vals.get("employee_id"):
                route = self.env["sale.route"].browse(vals["route_id"])
                if len(route.ss_employee_ids) == 1:
                    vals["employee_id"] = route.ss_employee_ids.id
        return super().create(vals_list)

    @api.constrains("employee_id", "route_id")
    def _check_employee_route(self):
        for plan in self:
            route_employees = plan.route_id.ss_employee_ids
            if route_employees and plan.employee_id not in route_employees:
                raise ValidationError(_("The selected route is not assigned to this employee."))

    def _prepare_plan_line_commands(self, route, clear=True):
        commands = [(5, 0, 0)] if clear else []
        for route_line in route.route_line_ids.filtered("active"):
            commands.append((0, 0, {
                "sequence": route_line.sequence,
                "outlet_id": route_line.outlet_id.id,
                "expected_visit_time": route_line.expected_visit_time,
            }))
        return commands

    def action_confirm(self):
        for plan in self:
            if not plan.route_id.distributor_contact_id:
                raise ValidationError(_("Please set a distributor on the route before confirming."))
            if not plan.plan_line_ids:
                raise ValidationError(_("Please add at least one planned outlet before confirming."))
        self.write({"state": "confirmed"})

    def action_start(self):
        for plan in self:
            if plan.state != "draft":
                raise ValidationError(_("Only draft plans can be started."))
        self.write({"state": "in_progress"})

    def action_done(self):
        for plan in self:
            if any(line.state == "pending" for line in plan.plan_line_ids):
                raise ValidationError(_("Please mark all planned outlets as visited or skipped before completing."))
        self.write({"state": "done"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_draft(self):
        self.write({"state": "draft"})

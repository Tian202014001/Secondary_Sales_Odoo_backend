# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SSRouteVisit(models.Model):
    _name = "sale.route.visit"
    _description = "Route Visit"
    _order = "visit_date desc, employee_id, route_id"

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
    visit_date = fields.Date(
        string="Visit Date",
        required=True,
        default=fields.Date.context_today,
    )
    source = fields.Selection(
        selection=[
            ("employee_selected", "Employee Selected"),
            ("management_plan", "Management Plan"),
        ],
        default="employee_selected",
        required=True,
    )
    plan_id = fields.Many2one(
        "sale.route.visit.plan",
        string="Visit Plan",
        domain="[('state', '=', 'confirmed')]",
    )
    distributor_contact_id = fields.Many2one(
        "res.partner",
        string="Distributor Contact",
        related="route_id.distributor_contact_id",
        store=True,
        readonly=True,
    )
    state = fields.Selection(
        selection=[
            ("draft", "Draft"),
            ("started", "Started"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        required=True,
    )
    visit_line_ids = fields.One2many(
        "sale.route.visit.line",
        "visit_id",
        string="Outlet Visits",
    )
    start_time = fields.Datetime(string="Start Time", readonly=True)
    end_time = fields.Datetime(string="End Time", readonly=True)

    @api.depends("employee_id", "route_id", "visit_date")
    def _compute_name(self):
        for visit in self:
            parts = [value for value in [
                visit.employee_id.name,
                visit.route_id.name,
                visit.visit_date and fields.Date.to_string(visit.visit_date),
            ] if value]
            visit.name = " / ".join(parts) or _("New Route Visit")

    @api.onchange("plan_id")
    def _onchange_plan_id(self):
        if not self.plan_id:
            return
        self.source = "management_plan"
        self.employee_id = self.plan_id.employee_id
        self.route_id = self.plan_id.route_id
        self.visit_date = self.plan_id.visit_date
        self.visit_line_ids = self._prepare_visit_line_commands_from_plan(self.plan_id)

    @api.onchange("route_id")
    def _onchange_route_id(self):
        if not self.route_id or self.plan_id:
            return
        if len(self.route_id.ss_employee_ids) == 1 and not self.employee_id:
            self.employee_id = self.route_id.ss_employee_ids.id
        self.visit_line_ids = self._prepare_visit_line_commands_from_route(self.route_id)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("plan_id"):
                plan = self.env["sale.route.visit.plan"].browse(vals["plan_id"])
                vals.setdefault("source", "management_plan")
                vals.setdefault("employee_id", plan.employee_id.id)
                vals.setdefault("route_id", plan.route_id.id)
                vals.setdefault("visit_date", plan.visit_date)
                if not vals.get("visit_line_ids"):
                    vals["visit_line_ids"] = self._prepare_visit_line_commands_from_plan(plan, clear=False)
            elif vals.get("route_id") and not vals.get("visit_line_ids"):
                route = self.env["sale.route"].browse(vals["route_id"])
                vals["visit_line_ids"] = self._prepare_visit_line_commands_from_route(route, clear=False)
                if not vals.get("employee_id") and len(route.ss_employee_ids) == 1:
                    vals["employee_id"] = route.ss_employee_ids.id
        return super().create(vals_list)

    @api.constrains("employee_id", "route_id")
    def _check_employee_route(self):
        for visit in self:
            route_employees = visit.route_id.ss_employee_ids
            if route_employees and visit.employee_id not in route_employees:
                raise ValidationError(_("The selected route is not assigned to this employee."))

    @api.constrains("route_id", "state")
    def _check_single_started_visit_per_route(self):
        for visit in self.filtered(lambda record: record.state == "started"):
            visit._ensure_route_not_already_started()

    def _ensure_route_not_already_started(self):
        self.ensure_one()
        existing_visit = self.search([
            ("id", "!=", self.id),
            ("route_id", "=", self.route_id.id),
            ("state", "=", "started"),
        ], limit=1)
        if existing_visit:
            raise ValidationError(
                _("Route %(route)s is already being visited by %(employee)s.")
                % {
                    "route": self.route_id.display_name,
                    "employee": existing_visit.employee_id.display_name,
                }
            )

    def _prepare_visit_line_commands_from_route(self, route, clear=True):
        commands = [(5, 0, 0)] if clear else []
        for route_line in route.route_line_ids.filtered("active"):
            commands.append((0, 0, {
                "sequence": route_line.sequence,
                "outlet_id": route_line.outlet_id.id,
                "expected_visit_time": route_line.expected_visit_time,
            }))
        return commands

    def _prepare_visit_line_commands_from_plan(self, plan, clear=True):
        commands = [(5, 0, 0)] if clear else []
        for plan_line in plan.plan_line_ids:
            commands.append((0, 0, {
                "sequence": plan_line.sequence,
                "outlet_id": plan_line.outlet_id.id,
                "expected_visit_time": plan_line.expected_visit_time,
            }))
        return commands

    def action_start(self):
        for visit in self:
            if visit.state != "draft":
                raise ValidationError(_("Only draft route visits can be started."))
            if not visit.visit_line_ids:
                raise ValidationError(_("Please add at least one outlet before starting the visit."))
            visit._ensure_route_not_already_started()
        self.write({
            "state": "started",
            "start_time": fields.Datetime.now(),
        })

    def action_done(self):
        for visit in self:
            if visit.state != "started":
                raise ValidationError(_("Only started route visits can be completed."))
            if any(line.state == "pending" for line in visit.visit_line_ids):
                raise ValidationError(_("Please mark all outlets as visited or skipped before completing."))
        self.write({
            "state": "done",
            "end_time": fields.Datetime.now(),
        })

    def action_cancel(self):
        for visit in self:
            if visit.state == "done":
                raise ValidationError(_("Completed route visits cannot be cancelled."))
        self.write({"state": "cancelled"})

    def action_reset_draft(self):
        for visit in self:
            if visit.state not in ("started", "cancelled"):
                raise ValidationError(_("Only started or cancelled route visits can be reset."))
        self.write({
            "state": "draft",
            "start_time": False,
            "end_time": False,
        })

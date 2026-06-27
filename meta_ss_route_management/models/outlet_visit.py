# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

class OutletVisit(models.Model):
    _name = "outlet.visit"
    _description = "Outlet Visit"
    _inherit = ['mail.thread', 'mail.activity.mixin']   

    employee_id = fields.Many2one(
        'hr.employee',
        string="Employee",
        required=True,
        tracking=True,
    )
    outlet_id = fields.Many2one(
        'res.partner',
        string="Outlet",
        domain="[('customer_type', '=', 'outlet')]",
        required=True,
        tracking=True,
    )
    check_in_time = fields.Datetime(
        string="Check In Time",
        tracking=True,
    )
    check_out_time = fields.Datetime(
        string="Check Out Time",
        tracking=True,
    )
    join_visit_id = fields.Many2one(
        'outlet.visit',
        string="Join Visit",
        help="Reference to the related join visit record if applicable.",
        tracking=True,
    )
    role_id = fields.Many2one(
        'res.mobile.user.group',
        related='employee_id.mobile_user_group_id',
        string="Role"
    )
    visit_type = fields.Selection(
        [('standard', 'Standard Visit'), ('join', 'Join Visit')],
        string="Visit Type",
        default='standard'
    )
    visited_with_id = fields.Many2one(
        'hr.employee',
        string="Visited With",
        help="Employee accompanying this visit.",
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        visits = super().create(vals_list)
        visits.with_context(syncing_visit_links=True)._link_visits()
        return visits

    def write(self, vals):
        if self.env.context.get('syncing_visit_links'):
            return super().write(vals)

        res = super().write(vals)
        self.with_context(syncing_visit_links=True)._link_visits()
        return res

    def _link_visits(self):
        """Unified method to establish the link between joint visits and standard visits."""
        from datetime import datetime, time
        for visit in self:
            if visit.visit_type == 'join':
                if not visit.visited_with_id or not visit.outlet_id or not visit.check_in_time:
                    continue
                check_in_date = visit.check_in_time.date()
                date_start = datetime.combine(check_in_date, time.min)
                date_end = datetime.combine(check_in_date, time.max)
                candidates = self.search([
                    ('visit_type', '=', 'standard'),
                    ('employee_id', '=', visit.visited_with_id.id),
                    ('outlet_id', '=', visit.outlet_id.id),
                    ('check_in_time', '>=', date_start),
                    ('check_in_time', '<=', date_end),
                ])
                matching_visit = False
                for cand in candidates:
                    overlap = True
                    if visit.check_out_time and cand.check_in_time > visit.check_out_time:
                        overlap = False
                    if cand.check_out_time and cand.check_out_time < visit.check_in_time:
                        overlap = False
                    if overlap:
                        matching_visit = cand
                        break
                if matching_visit:
                    if matching_visit.join_visit_id != visit:
                        matching_visit.with_context(syncing_visit_links=True).write({'join_visit_id': visit.id})
            elif visit.visit_type == 'standard':
                if not visit.employee_id or not visit.outlet_id or not visit.check_in_time:
                    continue
                check_in_date = visit.check_in_time.date()
                date_start = datetime.combine(check_in_date, time.min)
                date_end = datetime.combine(check_in_date, time.max)
                candidates = self.search([
                    ('visit_type', '=', 'join'),
                    ('visited_with_id', '=', visit.employee_id.id),
                    ('outlet_id', '=', visit.outlet_id.id),
                    ('check_in_time', '>=', date_start),
                    ('check_in_time', '<=', date_end),
                ])
                matching_visit = False
                for cand in candidates:
                    overlap = True
                    if visit.check_out_time and cand.check_in_time > visit.check_out_time:
                        overlap = False
                    if cand.check_out_time and cand.check_out_time < visit.check_in_time:
                        overlap = False
                    if overlap:
                        matching_visit = cand
                        break
                if matching_visit:
                    if visit.join_visit_id != matching_visit:
                        visit.with_context(syncing_visit_links=True).write({'join_visit_id': matching_visit.id})


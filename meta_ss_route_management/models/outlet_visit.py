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

    @api.model_create_multi
    def create(self, vals_list):
        visits = super().create(vals_list)
        for visit in visits:
            if visit.visit_type == 'join':
                visit._link_to_standard_visit()
        return visits

    def write(self, vals):
        res = super().write(vals)
        for visit in self:
            if visit.visit_type == 'join':
                visit._link_to_standard_visit()
        return res

    def _link_to_standard_visit(self):
        """Automatically assigns this join visit to the matching standard visit's join_visit_id."""
        self.ensure_one()
        if not self.visited_with_id or not self.outlet_id or not self.check_in_time or not self.check_out_time:
            return

        domain = [
            ('visit_type', '=', 'standard'),
            ('employee_id', '=', self.visited_with_id.id),
            ('outlet_id', '=', self.outlet_id.id),
            ('check_in_time', '<=', self.check_out_time),
            ('check_out_time', '>=', self.check_in_time),
        ]
        standard_visit = self.search(domain, order="check_in_time desc", limit=1)
        if standard_visit:
            standard_visit.join_visit_id = self.id

    visited_with_id = fields.Many2one(
        'hr.employee',
        string="Visited With",
        help="Employee accompanying this visit.",
        tracking=True,
    )
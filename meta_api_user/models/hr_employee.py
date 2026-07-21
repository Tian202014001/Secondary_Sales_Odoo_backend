# -*- coding: utf-8 -*-

from odoo import fields, models

class HrEmployee(models.Model):
    _inherit = "hr.employee"
    
    mobile_user_group_id = fields.Many2one(
        'res.mobile.user.group',
        string="Mobile User Group",
        help="The mobile role/group assigned to this employee.",
        required=True,
    )

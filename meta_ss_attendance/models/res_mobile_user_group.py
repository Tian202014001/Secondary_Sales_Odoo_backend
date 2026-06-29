# -*- coding: utf-8 -*-
from odoo import fields, models

class ResMobileUserGroup(models.Model):
    _inherit = 'res.mobile.user.group'

    skip_attendance_geolocation = fields.Boolean(
        string="Skip Attendance Geo-location",
        help="If checked, users in this group will not be subject to geo-location radius checks when punching attendance."
    )

# -*- coding: utf-8 -*-

import logging
from datetime import timedelta
from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class SalesEmployeeLocation(models.Model):
    _name = "sales.employee.location"
    _description = "Sales Employee GPS Location Log"
    _order = "recorded_at desc, id desc"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        ondelete="cascade",
        index=True,
    )
    attendance_id = fields.Many2one(
        "hr.attendance",
        string="Attendance Session",
        required=True,
        ondelete="cascade",
        index=True,
    )
    latitude = fields.Float(string="Latitude", digits=(10, 7), required=True)
    longitude = fields.Float(string="Longitude", digits=(10, 7), required=True)
    recorded_at = fields.Datetime(string="Recorded Timestamp", required=True, index=True)
    is_mock = fields.Boolean(string="Mock Location", default=False)

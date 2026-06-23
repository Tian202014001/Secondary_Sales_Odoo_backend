# -*- coding: utf-8 -*-

from odoo import models, fields

class MobileDevice(models.Model):
    _name = 'res.mobile.device'
    _description = 'Mobile Device'

    mobile_user_id = fields.Many2one(
        'res.mobile.user',
        required=True,
        ondelete='cascade',
    )
    employee_id = fields.Many2one('hr.employee')
    fcm_token = fields.Char(required=True, index=True)
    platform = fields.Selection([
        ('android', 'Android'),
        ('ios', 'iOS'),
        ('web', 'Web'),
    ], required=True)
    device_name = fields.Char()
    app_version = fields.Char()
    active = fields.Boolean(default=True)
    last_seen_at = fields.Datetime()

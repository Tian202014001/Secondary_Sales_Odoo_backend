# -*- coding: utf-8 -*-

from odoo import models, fields


class MobilePushNotification(models.Model):
    _name = 'mobile.push.notification'
    _description = 'Mobile Push Notification'

    notification_type = fields.Selection([
        ('sale_order_confirmed', 'Sale Order Confirmed'),
        ('sale_order_cancelled', 'Sale Order Cancelled'),
        ('sale_order_created', 'Sale Order Created'),
        ('primary_order_submitted', 'Primary Order Submitted'),
        ('delivery_validation_required', 'Delivery Validation Required'),
        ('delivery_order_validated', 'Delivery Order Validated'),
        ('leave_request_created', 'Leave Request Created'),
        ('leave_request_approved', 'Leave Request Approved'),
        ('expense_created', 'Expense Created'),
        ('expense_approved', 'Expense Approved'),
    ], default='sale_order_confirmed', required=True, index=True)
    mobile_user_id = fields.Many2one('res.mobile.user', required=True, index=True)
    sale_order_id = fields.Many2one('sale.order', index=True)
    title = fields.Char(required=True)
    body = fields.Text(required=True)
    payload_json = fields.Text()
    sent_device_ids = fields.Many2many(
        'res.mobile.device',
        'mobile_push_notification_device_rel',
        'notification_id',
        'device_id',
        string='Sent Devices',
        copy=False,
    )
    state = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ], default='pending', index=True)
    provider_message_id = fields.Char()
    error_message = fields.Text()
    retry_count = fields.Integer(default=0)
    sent_at = fields.Datetime()

    _sql_constraints = [
        (
            'mobile_push_unique_sale_order_user_type',
            'unique(notification_type, sale_order_id, mobile_user_id)',
            'A mobile push notification already exists for this sale order, mobile user, and notification type.',
        ),
    ]

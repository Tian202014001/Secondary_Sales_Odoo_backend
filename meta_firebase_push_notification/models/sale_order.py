# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    mobile_user_id = fields.Many2one(
        'res.mobile.user',
        string='Mobile User',
        index=True,
        copy=False,
    )

    @api.model_create_multi
    def create(self, vals_list):
        mobile_user_id = self.env.context.get('mobile_api_user_id')
        if mobile_user_id:
            for vals in vals_list:
                vals.setdefault('mobile_user_id', mobile_user_id)
        return super().create(vals_list)

    def action_confirm(self):
        orders_to_notify = self.filtered(
            lambda order: order.mobile_user_id and order.state not in ('sale', 'done', 'cancel')
        )
        res = super().action_confirm()
        for order in orders_to_notify.filtered(lambda order: order.state in ('sale', 'done')):
            order._create_mobile_confirmation_notification()
        return res

    def _create_mobile_confirmation_notification(self):
        self.ensure_one()
        if not self.mobile_user_id:
            return False

        payload = {
            'type': 'sale_order_confirmed',
            'model': 'sale.order',
            'id': self.id,
            'name': self.name,
        }
        vals = {
            'notification_type': 'sale_order_confirmed',
            'mobile_user_id': self.mobile_user_id.id,
            'sale_order_id': self.id,
            'title': 'Sale Order Confirmed',
            'body': f'Your sale order {self.name} has been confirmed.',
            'payload_json': json.dumps(payload),
        }

        Notification = self.env['mobile.push.notification'].sudo()
        existing = Notification.search([
            ('notification_type', '=', vals['notification_type']),
            ('sale_order_id', '=', self.id),
            ('mobile_user_id', '=', self.mobile_user_id.id),
        ], limit=1)
        return existing or Notification.create(vals)

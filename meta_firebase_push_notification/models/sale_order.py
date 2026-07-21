# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _name = 'sale.order'
    _inherit = ['sale.order', 'mobile.notification.mixin']

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
        records = super().create(vals_list)
        
        for record in records:
            if getattr(record, 'sale_type', False) == 'primary':
                _logger.info("Triggering Finance Admin notification for Primary Sale Order: %s", record.name)
                record._notify_finance_admins_of_primary_order()
                
        return records

    def _notify_finance_admins_of_primary_order(self):
        self.ensure_one()
        customer_name = self.partner_id.name or "Unknown Customer"
        creator_name = self.mobile_user_id.name if self.mobile_user_id else (self.create_uid.name or "Unknown User")
        
        self._notify_group_mobile_users(
            group_xml_id='meta_ss_sales.group_ss_finance_team',
            notification_type='primary_order_submitted',
            title='New Primary Order Submitted',
            body=f"Order #{self.name} for {customer_name} submitted by {creator_name}. Awaiting confirmation.",
            action_link=f"/orders/finance-confirm/{self.id}"
        )

    def _notify_supply_chain_coordinators(self):
        self.ensure_one()
        self._notify_group_mobile_users(
            group_xml_id='meta_ss_sales.group_ss_supply_chain_coordinator',
            notification_type='delivery_validation_required',
            title='Delivery Validation Required',
            body=f"Order #{self.name} is approved. Please validate delivery and inventory dispatch.",
            action_link=f"/supply-chain/validate/{self.id}"
        )

    def action_confirm(self):
        orders_to_notify = self.filtered(
            lambda order: order.mobile_user_id and order.state not in ('sale', 'done', 'cancel')
        )
        res = super().action_confirm()
        for order in orders_to_notify.filtered(lambda order: order.state in ('sale', 'done')):
            order._create_mobile_notification(
                'sale_order_confirmed',
                'Sale Order Confirmed',
                f'Your sale order {order.name} has been confirmed.'
            )
            # Notify manager if exists
            manager = order.mobile_user_id.employee_id.parent_id
            if manager:
                manager_mobile_users = self.env['res.mobile.user'].sudo().search([('employee_id', '=', manager.id)])
                for manager_user in manager_mobile_users:
                    order._create_mobile_notification(
                        'sale_order_confirmed',
                        'Team Sale Order Confirmed',
                        f'Sale order {order.name} by {order.mobile_user_id.name} has been confirmed.',
                        target_user=manager_user
                    )
            
            # Notify Supply Chain Coordinators if it's a primary order
            if getattr(order, 'sale_type', False) == 'primary':
                _logger.info("Triggering Supply Chain Coordinator notification for Primary Sale Order: %s", order.name)
                order._notify_supply_chain_coordinators()
                
        return res

    def _action_cancel(self):
        orders_to_notify = self.filtered(lambda order: order.mobile_user_id and order.state != 'cancel')
        res = super()._action_cancel()
        for order in orders_to_notify.filtered(lambda order: order.state == 'cancel'):
            order._create_mobile_notification(
                'sale_order_cancelled',
                'Sale Order Cancelled',
                f'Your sale order {order.name} has been cancelled.'
            )
        return res


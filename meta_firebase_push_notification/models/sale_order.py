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
        order_url = f"{self.get_base_url()}/web#id={self.id}&model=sale.order&view_type=form"
        self._notify_group_by_email(
            group_xml_id='meta_ss_sales.group_ss_finance_team',
            template_xml_id='meta_firebase_push_notification.email_template_primary_order_submitted',
            action_link=order_url
        )

    def _notify_supply_chain_coordinators(self):
        self.ensure_one()
        # Find the delivery order (stock.picking) associated with this sale order
        picking = self.picking_ids.filtered(lambda p: p.state != 'cancel')[:1] or self.picking_ids[:1]
        base_url = self.get_base_url()
        
        if picking:
            target_url = f"{base_url}/web#id={picking.id}&model=stock.picking&view_type=form"
        else:
            target_url = f"{base_url}/web#id={self.id}&model=sale.order&view_type=form"

        # Mobile push notification for Supply Chain Coordinators
        self._notify_group_mobile_users(
            group_xml_id='meta_ss_sales.group_ss_supply_chain_coordinator',
            notification_type='delivery_validation_required',
            title='Delivery Validation Required',
            body=f"Order #{self.name} is approved. Please validate delivery and inventory dispatch.",
            action_link=target_url
        )
        # Additional email notification for Supply Chain Coordinators
        self._notify_group_by_email(
            group_xml_id='meta_ss_sales.group_ss_supply_chain_coordinator',
            template_xml_id='meta_firebase_push_notification.email_template_delivery_validation_required',
            action_link=target_url
        )

    def action_confirm(self):
        res = super().action_confirm()
        for order in self.filtered(lambda o: o.state in ('sale', 'done')):
            # Mobile push notifications for mobile orders
            if order.mobile_user_id:
                order._create_mobile_notification(
                    'sale_order_confirmed',
                    'Sale Order Confirmed',
                    f'Your sale order {order.name} has been confirmed.'
                )
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

            # Notify Supply Chain Coordinators whenever a primary sale order is confirmed
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


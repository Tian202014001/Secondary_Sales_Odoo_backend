# -*- coding: utf-8 -*-

import json
import logging

from odoo import models

_logger = logging.getLogger(__name__)

class MobileNotificationMixin(models.AbstractModel):
    _name = 'mobile.notification.mixin'
    _description = 'Mobile Notification Mixin'

    def _notify_group_mobile_users(self, group_xml_id, notification_type, title, body, action_link=None):
        self.ensure_one()
        _logger.info("Checking for group '%s' to notify for %s %s...", group_xml_id, self._name, self.display_name)
        group = self.env.ref(group_xml_id, raise_if_not_found=False)
        if not group:
            _logger.warning("Group '%s' not found.", group_xml_id)
            return
            
        group_users = group.users
        group_employees = group_users.mapped('employee_id')
        
        if not group_employees:
            _logger.info("No employees linked to users in group '%s'.", group_xml_id)
            return
            
        mobile_users = self.env['res.mobile.user'].sudo().search([
            ('employee_id', 'in', group_employees.ids)
        ])
        
        if not mobile_users:
            _logger.info("No mobile users found for employees in group '%s'.", group_xml_id)
            return
            
        _logger.info("Found %d mobile users to notify in group '%s'. Dispatching...", len(mobile_users), group_xml_id)
        for user in mobile_users:
            self._create_mobile_notification(
                notification_type=notification_type,
                title=title,
                body=body,
                target_user=user,
                action_link=action_link
            )
        _logger.info("Successfully dispatched notifications to group '%s' for %s %s.", group_xml_id, self._name, self.display_name)

    def _create_mobile_notification(self, notification_type, title, body, target_user=None, action_link=None):
        self.ensure_one()
        user_to_notify = target_user or getattr(self, 'mobile_user_id', False)
        if not user_to_notify:
            return False

        payload = {
            'type': notification_type,
            'model': self._name,
            'id': self.id,
            'name': self.display_name,
        }
        if action_link:
            payload['action_link'] = action_link
            
        vals = {
            'notification_type': notification_type,
            'mobile_user_id': user_to_notify.id,
            'title': title,
            'body': body,
            'payload_json': json.dumps(payload),
        }
        
        domain = [
            ('notification_type', '=', vals['notification_type']),
            ('mobile_user_id', '=', user_to_notify.id),
        ]
        
        # Link sale_order_id if present to maintain unique constraint
        if self._name == 'sale.order':
            vals['sale_order_id'] = self.id
            domain.append(('sale_order_id', '=', self.id))
        elif getattr(self, 'sale_id', False):
            vals['sale_order_id'] = self.sale_id.id
            domain.append(('sale_order_id', '=', self.sale_id.id))

        Notification = self.env['mobile.push.notification'].sudo()
        
        # If we have a sale_order_id linked, we can check for existing notifications safely
        existing = False
        if 'sale_order_id' in vals:
            existing = Notification.search(domain, limit=1)
            
        return existing or Notification.create(vals)

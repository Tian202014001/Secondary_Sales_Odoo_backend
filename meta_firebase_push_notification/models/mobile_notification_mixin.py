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

    def _notify_employee(self, employee, notification_type, title, body, action_link=None):
        """Notify every mobile user linked to an employee.

        An employee with no mobile user is not an error: they simply don't use the
        app, so there is nobody to push to and the record is logged and skipped.
        Nothing an employee lacks may abort the business transaction that triggered
        the notification.
        """
        self.ensure_one()
        if not employee:
            return self.env['mobile.push.notification']

        mobile_users = self.env['res.mobile.user'].sudo().search([('employee_id', '=', employee.id)])
        if not mobile_users:
            _logger.info(
                "Employee %s has no mobile user; skipping %s notification for %s %s.",
                employee.display_name, notification_type, self._name, self.display_name,
            )
            return self.env['mobile.push.notification']

        notifications = self.env['mobile.push.notification'].sudo()
        for mobile_user in mobile_users:
            created = self._create_mobile_notification(
                notification_type=notification_type,
                title=title,
                body=body,
                target_user=mobile_user,
                action_link=action_link,
            )
            if created:
                notifications |= created

        _logger.info(
            "Queued %s notification(s) of type %s to %s for %s %s.",
            len(notifications), notification_type, employee.display_name, self._name, self.display_name,
        )
        return notifications

    def _notify_employee_manager(self, employee, notification_type, title, body, action_link=None):
        """Notify the mobile users of an employee's direct manager (parent_id)."""
        self.ensure_one()
        manager = employee.parent_id
        if not manager:
            _logger.info(
                "Employee %s has no manager (parent_id); skipping %s notification for %s %s.",
                employee.display_name, notification_type, self._name, self.display_name,
            )
            return self.env['mobile.push.notification']

        return self._notify_employee(manager, notification_type, title, body, action_link=action_link)

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

    def _notify_group_by_email(self, group_xml_id, template_xml_id, action_link=None):
        """Send an email notification to each user's employee work_email in an Odoo security group using a mail template."""
        self.ensure_one()
        group = self.env.ref(group_xml_id, raise_if_not_found=False)
        template = self.env.ref(template_xml_id, raise_if_not_found=False)
        if not group or not template:
            _logger.warning("Group '%s' or Template '%s' not found.", group_xml_id, template_xml_id)
            return

        # Collect work_email of each employee linked to users in the group
        recipient_emails = set()
        for user in group.users:
            # Prioritize employee work_email
            work_email = user.employee_id.work_email if user.employee_id else False
            email_to_use = work_email or user.email or (user.partner_id and user.partner_id.email)
            if email_to_use:
                recipient_emails.add(email_to_use.strip())

        if not recipient_emails:
            _logger.info("No recipient employee work_emails found for group '%s'.", group_xml_id)
            return

        record_url = action_link or f"{self.get_base_url()}/web#id={self.id}&model={self._name}&view_type=form"
        ctx = dict(self.env.context, action_link=record_url)

        # Send email to each recipient's employee work_email
        for email in recipient_emails:
            try:
                template.with_context(ctx).send_mail(
                    self.id,
                    email_values={'email_to': email},
                    force_send=True
                )
                _logger.info("Sent email notification using '%s' to employee work_email %s for %s %s", template_xml_id, email, self._name, self.display_name)
            except Exception as e:
                _logger.exception("Failed to send email to %s: %s", email, e)




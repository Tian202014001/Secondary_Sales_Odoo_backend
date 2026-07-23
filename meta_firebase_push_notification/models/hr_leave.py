# -*- coding: utf-8 -*-

import logging

from odoo import api, models


_logger = logging.getLogger(__name__)


class HrLeave(models.Model):
    _name = 'hr.leave'
    _inherit = ['hr.leave', 'mobile.notification.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        leaves = super().create(vals_list)
        for leave in leaves:
            leave._notify_manager_of_leave_request()
        return leaves

    def _notify_manager_of_leave_request(self):
        """Push to the requesting employee's direct manager when a leave is filed."""
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return

        _logger.info("Triggering Leave Request notification for %s by %s", self.display_name, employee.name)
        leave_url = f"{self.get_base_url()}/web#id={self.id}&model=hr.leave&view_type=form"
        body = (
            f"{employee.name} requested {self.holiday_status_id.name} "
            f"from {self.request_date_from} to {self.request_date_to} "
            f"({self.number_of_days:g} day(s))."
        )
        self._notify_employee_manager(
            employee,
            notification_type='leave_request_created',
            title='Leave Request Submitted',
            body=body,
            action_link=leave_url,
        )

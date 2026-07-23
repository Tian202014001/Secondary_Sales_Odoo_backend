# -*- coding: utf-8 -*-

import logging

from odoo import models


_logger = logging.getLogger(__name__)


class HrExpenseSheet(models.Model):
    _name = 'hr.expense.sheet'
    _inherit = ['hr.expense.sheet', 'mobile.notification.mixin']

    def _do_submit(self):
        """Hooked instead of create(): the mobile API creates the sheet first and links
        the expense lines afterwards, so at create() time the report has no amount yet
        and the manager has nothing actionable. _do_submit is the funnel both
        action_submit_sheet() and the backend button go through.
        """
        res = super()._do_submit()
        for sheet in self:
            sheet._notify_manager_of_expense_report()
        return res

    def _do_approve(self):
        """Sheets are selected before super(): _do_approve only acts on the ones in
        submit/draft, and their state has already moved on by the time it returns.
        """
        sheets_to_notify = self.filtered(lambda s: s.state in {'submit', 'draft'})
        res = super()._do_approve()
        for sheet in sheets_to_notify:
            sheet._notify_employee_of_expense_approval()
        return res

    def _notify_employee_of_expense_approval(self):
        """Push back to the submitting employee once their report is approved."""
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return

        _logger.info("Triggering Expense Approved notification for %s to %s", self.display_name, employee.name)
        sheet_url = f"{self.get_base_url()}/web#id={self.id}&model=hr.expense.sheet&view_type=form"
        body = (
            f"Your expense report '{self.name}' for "
            f"{self.total_amount:.2f} {self.currency_id.name or ''} has been approved."
        )
        self._notify_employee(
            employee,
            notification_type='expense_approved',
            title='Expense Report Approved',
            body=body.strip(),
            action_link=sheet_url,
        )

    def _notify_manager_of_expense_report(self):
        """Push to the submitting employee's direct manager when a report is submitted."""
        self.ensure_one()
        employee = self.employee_id
        if not employee:
            return

        _logger.info("Triggering Expense Report notification for %s by %s", self.display_name, employee.name)
        sheet_url = f"{self.get_base_url()}/web#id={self.id}&model=hr.expense.sheet&view_type=form"
        body = (
            f"{employee.name} submitted expense report '{self.name}' "
            f"for {self.total_amount:.2f} {self.currency_id.name or ''}."
        )
        self._notify_employee_manager(
            employee,
            notification_type='expense_created',
            title='Expense Report Submitted',
            body=body.strip(),
            action_link=sheet_url,
        )

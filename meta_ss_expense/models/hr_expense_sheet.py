# -*- coding: utf-8 -*-
from odoo import models, fields, _
from odoo.exceptions import ValidationError

class HrExpenseSheet(models.Model):
    _inherit = 'hr.expense.sheet'

    request_source = fields.Selection([
        ('odoo', 'Odoo'),
        ('app', 'Mobile App')
    ], string="Request Source", default="odoo", required=True)

    description = fields.Text(string="Description")

    def _check_app_workflow_policy(self, action_name):
        """
        Enforce strict validation:
        Only the employee's direct manager (parent_id) can approve/refuse.
        """
        for sheet in self:
            # Bypass logic if the current user is a superuser/admin to prevent getting stuck
            if not self.env.is_admin():
                mobile_api_user_id = self.env.context.get('mobile_api_user_id')
                if mobile_api_user_id:
                    mobile_user = self.env['res.mobile.user'].sudo().browse(mobile_api_user_id)
                    current_employee = mobile_user.employee_id
                else:
                    current_employee = self.env.user.employee_id

                if not current_employee:
                    raise ValidationError(_("You must be linked to an employee to %s expenses.") % action_name)
                
                if sheet.employee_id.parent_id != current_employee:
                    raise ValidationError(
                        _("Strict Policy: Only %s (Direct Manager) can %s this expense sheet.") 
                        % (sheet.employee_id.parent_id.name, action_name)
                    )

    def action_approve_expense_sheets(self):
        self._check_app_workflow_policy('approve')
        return super(HrExpenseSheet, self).action_approve_expense_sheets()

    def action_refuse_expense_sheets(self):
        self._check_app_workflow_policy('refuse')
        return super(HrExpenseSheet, self).action_refuse_expense_sheets()

    def _do_refuse(self, reason):
        self._check_app_workflow_policy('refuse')
        return super(HrExpenseSheet, self)._do_refuse(reason)

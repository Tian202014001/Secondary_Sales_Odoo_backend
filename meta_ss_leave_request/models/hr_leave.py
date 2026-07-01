from odoo import models, fields, api
from odoo.exceptions import ValidationError

class HrLeave(models.Model):
    _inherit = 'hr.leave'

    request_source = fields.Selection([
        ('odoo', 'Odoo'),
        ('app', 'Mobile App')
    ], string="Request Source", default="odoo")

    def action_approve(self):
        """
        Override approval to enforce strict custom logic for app requests.
        Only the employee's direct manager can approve app-generated leaves.
        """
        for leave in self:
            if leave.request_source == 'app':
                # Bypass logic if the current user is a superuser/admin to prevent getting stuck
                if not self.env.is_admin():
                    mobile_api_user_id = self.env.context.get('mobile_api_user_id')
                    if mobile_api_user_id:
                        mobile_user = self.env['res.mobile.user'].sudo().browse(mobile_api_user_id)
                        current_employee = mobile_user.employee_id
                    else:
                        current_employee = self.env.user.employee_id

                    if not current_employee:
                        raise ValidationError("You must be linked to an employee to approve leaves.")
                    
                    if leave.employee_id.parent_id != current_employee:
                        raise ValidationError(
                            f"Strict Policy: Only {leave.employee_id.parent_id.name} (Direct Manager) "
                            f"can approve this leave request from the mobile app."
                        )
        return super(HrLeave, self).action_approve()

    def action_refuse(self):
        """
        Override refusal to enforce strict custom logic for app requests.
        Only the employee's direct manager can refuse app-generated leaves.
        """
        for leave in self:
            if leave.request_source == 'app':
                # Bypass logic if the current user is a superuser/admin
                if not self.env.is_admin():
                    mobile_api_user_id = self.env.context.get('mobile_api_user_id')
                    if mobile_api_user_id:
                        mobile_user = self.env['res.mobile.user'].sudo().browse(mobile_api_user_id)
                        current_employee = mobile_user.employee_id
                    else:
                        current_employee = self.env.user.employee_id

                    if not current_employee:
                        raise ValidationError("You must be linked to an employee to refuse leaves.")
                    
                    if leave.employee_id.parent_id != current_employee:
                        raise ValidationError(
                            f"Strict Policy: Only {leave.employee_id.parent_id.name} (Direct Manager) "
                            f"can refuse this leave request from the mobile app."
                        )
        return super(HrLeave, self).action_refuse()

    @api.constrains('number_of_days', 'date_from', 'date_to')
    def _check_zero_duration(self):
        for leave in self:
            if leave.date_from and leave.date_to and leave.number_of_days == 0:
                raise ValidationError(
                    "The requested period has 0 working days (e.g., falls entirely on weekends or public holidays)."
                )

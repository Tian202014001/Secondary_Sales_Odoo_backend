# -*- coding: utf-8 -*-

import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class ResUsers(models.Model):
    _inherit = 'res.users'

    mobile_user_id = fields.Many2one(
        'res.mobile.user',
        string="Mobile App User",
        compute="_compute_mobile_user_id",
        help="Linked Mobile User record associated with this system user.",
    )

    def _compute_mobile_user_id(self):
        for user in self:
            employee = self.env['hr.employee'].sudo().search([('user_id', '=', user.id)], limit=1)
            if employee:
                user.mobile_user_id = self.env['res.mobile.user'].sudo().search([('employee_id', '=', employee.id)], limit=1)
            else:
                user.mobile_user_id = False

    @api.model_create_multi
    def create(self, vals_list):
        # Capture raw password before create consumes or hashes it
        passwords = [vals.get('password') for vals in vals_list]
        
        users = super().create(vals_list)
        
        for user, raw_password in zip(users, passwords):
            try:
                user._create_employee_and_mobile_user(raw_password=raw_password)
            except Exception as e:
                _logger.warning("Failed to auto-create employee or mobile user for user %s (ID %s): %s", user.name, user.id, str(e))
                
        return users

    def _create_employee_and_mobile_user(self, raw_password=None):
        self.ensure_one()
        
        # 1. Check or Create hr.employee
        HrEmployee = self.env['hr.employee'].sudo()
        employee = HrEmployee.search([('user_id', '=', self.id)], limit=1)
        
        if not employee:
            mobile_group_id = self.env.context.get('default_mobile_user_group_id')
            email = self.email or self.login
            user_phone = self.phone or False
            user_mobile = getattr(self, 'mobile', False) or False
            
            emp_vals = {
                'name': self.name,
                'user_id': self.id,
                'company_id': self.company_id.id if self.company_id else self.env.company.id,
                'work_email': email,
            }
            if mobile_group_id:
                emp_vals['mobile_user_group_id'] = mobile_group_id
            if user_phone:
                emp_vals['work_phone'] = user_phone
            if user_mobile:
                emp_vals['mobile_phone'] = user_mobile
                
            employee = HrEmployee.create(emp_vals)


        # 2. Check or Create res.mobile.user
        ResMobileUser = self.env['res.mobile.user'].sudo()
        mobile_user = ResMobileUser.search([('employee_id', '=', employee.id)], limit=1)
        
        if not mobile_user:
            email = self.email or self.login or False
            user_phone = self.phone or False
            user_mobile = getattr(self, 'mobile', False) or False
            phone = user_mobile or user_phone or False
            
            # Avoid duplicate phone/email constraint errors
            if phone and ResMobileUser.search([('phone', '=', phone)], limit=1):
                phone = False
            if email and ResMobileUser.search([('email', '=', email)], limit=1):
                email = f"user_{self.id}_{email}"
                
            password_to_use = raw_password or getattr(self, 'password', False) or self.login or "123456"
            
            mobile_user_vals = {
                'name': self.name,
                'employee_id': employee.id,
                'company_id': self.company_id.id if self.company_id else self.env.company.id,
                'email': email,
                'phone': phone,
                'password': password_to_use,
                'active': self.active,
            }
            mobile_user = ResMobileUser.create(mobile_user_vals)

            
        return mobile_user
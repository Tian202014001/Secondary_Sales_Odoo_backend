# -*- coding: utf-8 -*-

from odoo.exceptions import AccessDenied
from odoo.osv import expression


class MobilePolicy:
    """Centralized mobile authorization policy for model access and rules."""

    def __init__(self, mobile_user):
        self.mobile_user = mobile_user.sudo() if mobile_user else mobile_user

    @property
    def group(self):
        return self.mobile_user.sudo().group_id if self.mobile_user else False

    def ensure_group(self):
        if not self.group:
            raise AccessDenied("The mobile user has no assigned mobile group.")
        return self.group

    def has_model_access(self, model_name, operation, default_if_unconfigured=True):
        group = self.ensure_group()
        operation = (operation or "").strip()
        if operation not in ("read", "create", "write", "unlink"):
            return False

        access_records = group._get_effective_mobile_groups().mapped("model_access_ids").sudo().filtered(
            lambda access: access.model_id.model == model_name
        )
        if not access_records:
            return bool(default_if_unconfigured)

        return any(access_records.mapped("perm_%s" % operation))

    def rule_domain(self, model_name, operation):
        group = self.ensure_group()
        operation = (operation or "").strip()
        if operation not in ("read", "create", "write", "unlink"):
            return []

        return group.get_mobile_rule_domain(model_name, operation, mobile_user=self.mobile_user)

    def apply_domain(self, model_name, operation, domain):
        rule_domain = self.rule_domain(model_name, operation)
        if not rule_domain:
            return domain
        return expression.AND([domain, rule_domain])

    def allows_values(self, env, model_name, operation, values):
        rule_domain = self.rule_domain(model_name, operation)
        if not rule_domain:
            return True
        record = env[model_name].new(values or {})
        return bool(record.filtered_domain(rule_domain))

    @staticmethod
    def visible_distributor_ids(env, employee):
        employee = employee.sudo()
        if "effective_distributor_contact_ids" in employee._fields:
            return employee.effective_distributor_contact_ids.ids

        subordinate_employees = env["hr.employee"].sudo().search([
            ("id", "child_of", employee.id),
        ]) - employee
        if not subordinate_employees:
            subordinate_employees = employee
        return subordinate_employees.mapped("distributor_contact_ids").ids

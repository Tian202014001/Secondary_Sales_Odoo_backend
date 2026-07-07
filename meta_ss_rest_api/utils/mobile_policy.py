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

    def has_ui_access(self, key):
        """Whether the user's group may see/use the UI resource ``key``.

        Allowed if:
        - Resource is not registered or not associated with any module (not enforced).
        - User's group has the module containing the resource, AND the resource
          is not in the group's denylists (hidden_menu_ids / hidden_button_ids).
        """
        if not self.mobile_user:
            return False
        resource = self.mobile_user.env["mobile.ui.resource"].sudo().search(
            [("key", "=", key), ("active", "=", True)],
            limit=1,
        )
        if not resource or not resource.module_ids:
            return True
        group = self.group
        if not group:
            return False
            
        group_resources = group.module_ids.mapped("resource_ids")
        if resource not in group_resources:
            return False
            
        hidden = group.hidden_menu_ids | group.hidden_button_ids
        if resource in hidden:
            return False
            
        return True

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
        """Distributors visible to an employee via the manager hierarchy.

        Walks the hr.employee ``parent_id`` chain with ``child_of``: a manager
        sees the distributors assigned to all of their subordinates; an
        employee with no subordinates sees their own assigned distributors.
        Deliberately does NOT use ``effective_distributor_contact_ids`` so the
        list always reflects the live employee manager hierarchy.
        """
        employee = employee.sudo()
        subordinate_employees = env["hr.employee"].sudo().search([
            ("id", "child_of", employee.id),
        ]) - employee
        if not subordinate_employees:
            subordinate_employees = employee
        distributors = subordinate_employees.mapped("distributor_contact_ids")
        return distributors.filtered(
            lambda partner: partner.customer_type == "distributor"
        ).ids

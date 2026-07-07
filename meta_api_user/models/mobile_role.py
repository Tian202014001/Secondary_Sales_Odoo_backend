from odoo import api, fields, models
from odoo.osv import expression
from odoo.tools.safe_eval import safe_eval


class ResMobileUserGroup(models.Model):
    _name = "res.mobile.user.group"
    _description = "Mobile User Group"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    user_ids = fields.One2many("res.mobile.user", "group_id", string="Mobile Users")
    
    # Return / Scrap visibility & field permissions
    can_view_all_returns = fields.Boolean(
        string="Can View All Returns", 
        default=False,
        help="If checked, users bypass the manager hierarchy for returns & scraps."
    )
    can_edit_so_qty = fields.Boolean(
        string="Can Edit SO Qty",
        default=False,
    )
    can_edit_qc_qty = fields.Boolean(
        string="Can Edit QC Qty",
        default=False,
    )
    can_edit_effective_qty = fields.Boolean(
        string="Can Edit Effective Qty",
        default=False,
        help="Allows editing Odoo's native 'Done' quantity."
    )
    can_manage_access = fields.Boolean(
        string="Can Manage Access Catalog",
        default=False,
        help="Allows mobile users in this group to sync the app's UI resource "
        "catalog to Odoo (POST /api/v1/access/catalog/sync).",
    )

    module_ids = fields.Many2many(
        "ss.module",
        "res_mobile_user_group_ss_module_rel",
        "group_id",
        "module_id",
        string="Modules",
        help="Logical modules assigned to this group.",
    )
    hidden_menu_ids = fields.Many2many(
        "mobile.ui.resource",
        "res_mobile_user_group_hidden_menu_rel",
        "group_id",
        "resource_id",
        string="Hidden Menus",
        domain="[('res_type', '=', 'screen')]",
        help="Menu items hidden as exceptions for this group.",
    )
    hidden_button_ids = fields.Many2many(
        "mobile.ui.resource",
        "res_mobile_user_group_hidden_button_rel",
        "group_id",
        "resource_id",
        string="Hidden Buttons",
        domain="[('res_type', '=', 'action')]",
        help="Buttons/actions hidden as exceptions for this group.",
    )

    implied_group_ids = fields.Many2many(
        "res.mobile.user.group",
        "res_mobile_user_group_implied_rel",
        "group_id",
        "implied_group_id",
        string="Implied Groups",
    )
    model_access_ids = fields.Many2many(
        "ir.model.access",
        "res_mobile_user_group_model_access_rel",
        "group_id",
        "access_id",
        string="Mobile Model Access",
        help="Existing Odoo access records used as mobile API configuration only.",
    )
    rule_ids = fields.Many2many(
        "ir.rule",
        "res_mobile_user_group_rule_rel",
        "group_id",
        "rule_id",
        string="Mobile Record Rules",
        help="Existing Odoo record rules used as mobile API configuration only.",
    )
    effective_model_access_ids = fields.Many2many(
        "ir.model.access",
        compute="_compute_effective_permissions",
        string="Effective Mobile Model Access",
        help="Model access from this group and every implied mobile group.",
    )
    effective_rule_ids = fields.Many2many(
        "ir.rule",
        compute="_compute_effective_permissions",
        string="Effective Mobile Record Rules",
        help="Record rules from this group and every implied mobile group.",
    )
    effective_resource_ids = fields.Many2many(
        "mobile.ui.resource",
        compute="_compute_effective_ui_access",
        string="Effective UI Access",
        help="Screens & buttons this group actually gets: the resources of its "
        "assigned modules minus its Hidden Menus and Hidden Buttons. This is the "
        "same set delivered to the app as 'granted'.",
    )

    def _get_effective_mobile_groups(self):
        groups = self.browse()
        pending = self
        while pending:
            groups |= pending
            implied = pending.mapped("implied_group_ids") - groups
            pending = implied
        return groups

    def _compute_effective_permissions(self):
        for group in self:
            effective_groups = group._get_effective_mobile_groups()
            group.effective_model_access_ids = effective_groups.mapped("model_access_ids")
            group.effective_rule_ids = effective_groups.mapped("rule_ids")

    @api.depends(
        "module_ids",
        "module_ids.resource_ids",
        "hidden_menu_ids",
        "hidden_button_ids",
    )
    def _compute_effective_ui_access(self):
        for group in self:
            module_resources = group.module_ids.mapped("resource_ids").filtered("active")
            hidden = group.hidden_menu_ids | group.hidden_button_ids
            group.effective_resource_ids = module_resources - hidden

    def get_mobile_access_summary(self):
        self.ensure_one()
        groups = self._get_effective_mobile_groups()
        access_by_model = {}
        for access in groups.mapped("model_access_ids").sudo():
            model_name = access.model_id.model
            if not model_name:
                continue
            model_access = access_by_model.setdefault(
                model_name,
                {
                    "read": False,
                    "create": False,
                    "write": False,
                    "unlink": False,
                },
            )
            model_access["read"] = model_access["read"] or bool(access.perm_read)
            model_access["create"] = model_access["create"] or bool(access.perm_create)
            model_access["write"] = model_access["write"] or bool(access.perm_write)
            model_access["unlink"] = model_access["unlink"] or bool(access.perm_unlink)

        rules = []
        for rule in groups.mapped("rule_ids").sudo().filtered(lambda item: item.active):
            rules.append({
                "id": rule.id,
                "name": rule.name,
                "model": rule.model_id.model,
                "domain": rule.domain_force or "[]",
                "read": bool(rule.perm_read),
                "create": bool(rule.perm_create),
                "write": bool(rule.perm_write),
                "unlink": bool(rule.perm_unlink),
            })

        return {
            "models": access_by_model,
            "rules": rules,
        }

    def has_mobile_model_access(self, model_name, operation, default_if_unconfigured=True):
        self.ensure_one()
        operation = (operation or "").strip()
        if operation not in ("read", "create", "write", "unlink"):
            return False

        access_records = self._get_effective_mobile_groups().mapped("model_access_ids").sudo().filtered(
            lambda access: access.model_id.model == model_name
        )
        if not access_records:
            return bool(default_if_unconfigured)

        return any(access_records.mapped("perm_%s" % operation))

    def get_mobile_rule_domain(self, model_name, operation, mobile_user=None):
        self.ensure_one()
        operation = (operation or "").strip()
        if operation not in ("read", "create", "write", "unlink"):
            return []

        rules = self._get_effective_mobile_groups().mapped("rule_ids").sudo().filtered(
            lambda rule: rule.active
            and rule.model_id.model == model_name
            and getattr(rule, "perm_%s" % operation)
        )
        if not rules:
            return []

        mobile_user = mobile_user.sudo() if mobile_user else self.env["res.mobile.user"]
        employee = mobile_user.employee_id if mobile_user else self.env["hr.employee"]
        company = (
            employee.company_id
            or mobile_user.company_id
            or self.env.company
        )
        eval_context = {
            "user": self.env.user,
            "mobile_user": mobile_user,
            "employee": employee,
            "company_id": company.id,
            "company_ids": [company.id],
        }
        domains = []
        for rule in rules:
            domain = safe_eval(rule.domain_force or "[]", eval_context)
            if domain:
                domains.append(domain)
        return expression.OR(domains) if domains else []

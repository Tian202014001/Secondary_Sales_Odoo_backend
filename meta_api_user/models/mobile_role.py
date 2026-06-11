from odoo import api, fields, models


class ResMobileUserGroup(models.Model):
    _name = "res.mobile.user.group"
    _description = "Mobile User Group"
    _order = "name"

    name = fields.Char(required=True)
    code = fields.Char(required=True, index=True)
    active = fields.Boolean(default=True)
    user_ids = fields.One2many("res.mobile.user", "group_id", string="Mobile Users")
    
    implied_group_ids = fields.Many2many(
        "res.mobile.user.group",
        "res_mobile_user_group_implied_rel",
        "group_id",
        "implied_group_id",
        string="Implied Groups",
    )
    permission_ids = fields.Many2many(
        "res.mobile.permission",
        "res_mobile_user_group_permission_rel",
        "group_id",
        "permission_id",
        string="Direct Permissions",
    )
    effective_permission_ids = fields.Many2many(
        "res.mobile.permission",
        "res_mobile_user_group_effective_permission_rel",
        "group_id",
        "permission_id",
        string="Effective Permissions",
        compute="_compute_effective_permissions",
        store=True,
    )

    @api.depends("permission_ids", "implied_group_ids", "implied_group_ids.effective_permission_ids")
    def _compute_effective_permissions(self):
        for group in self:
            permissions = group.permission_ids
            for implied in group.implied_group_ids:
                permissions |= implied.effective_permission_ids
            group.effective_permission_ids = permissions

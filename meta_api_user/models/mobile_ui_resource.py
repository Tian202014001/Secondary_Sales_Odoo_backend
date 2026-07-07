# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MobileUiResource(models.Model):
    """Catalog of app screens and actions that can be gated per mobile group.

    The Flutter app owns the key namespace and syncs this catalog via
    ``POST /api/v1/access/catalog/sync``. Admins then grant keys to groups
    (``res.mobile.user.group.ui_resource_ids``) and flip ``enforced`` on the
    resources they want to actually gate.

    Hybrid semantics: a resource with ``enforced = False`` is visible to
    everyone (so newly-synced keys never hide existing features); once
    ``enforced = True`` it becomes an allowlist — only groups granted the key
    may see/use it. UI grants are per-group and are NOT inherited through
    ``implied_group_ids`` (unlike model/record access).
    """

    _name = "mobile.ui.resource"
    _description = "Mobile UI Resource (Screen/Action)"
    _order = "module, res_type, key"

    key = fields.Char(
        required=True,
        index=True,
        help="Stable app-owned identifier, e.g. 'screen.sales.order_create'.",
    )
    res_type = fields.Selection(
        [("screen", "Screen"), ("action", "Action")],
        string="Type",
        required=True,
        default="screen",
    )
    module = fields.Char(help="App module the resource belongs to, e.g. 'sales'.")
    label = fields.Char(string="Label", help="Human-friendly name for admins.")
    active = fields.Boolean(default=True)
    last_seen = fields.Char(
        string="Last Synced Version",
        help="App version that last synced this resource.",
    )
    module_ids = fields.Many2many(
        "ss.module",
        "ss_module_resource_rel",
        "resource_id",
        "module_id",
        string="Modules",
    )

    _sql_constraints = [
        ("key_uniq", "unique(key)", "The mobile UI resource key must be unique."),
    ]

    @api.model
    def get_access_payload(self, group=None):
        """Return ``{'enforced': [...keys], 'granted': [...keys]}`` for a group.

        - ``enforced``: every active resource currently associated with any module.
        - ``granted``: keys in group's modules minus its hidden screens and actions.
        """
        Resource = self.sudo()
        enforced_keys = Resource.search([
            ("module_ids", "!=", False),
            ("active", "=", True),
        ]).mapped("key")
        
        granted_keys = []
        if group:
            group_sudo = group.sudo()
            module_resources = group_sudo.module_ids.mapped("resource_ids").filtered("active")
            hidden = group_sudo.hidden_menu_ids | group_sudo.hidden_button_ids
            granted_keys = (module_resources - hidden).mapped("key")
            
        return {"enforced": enforced_keys, "granted": granted_keys}

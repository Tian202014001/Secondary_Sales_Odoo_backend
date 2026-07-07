# -*- coding: utf-8 -*-

from odoo import api, fields, models


class MobileUiResource(models.Model):
    """Catalog of app screens and actions that can be gated per mobile group.

    The Flutter app owns the key namespace and syncs this catalog via
    ``POST /api/v1/access/catalog/sync``. Each resource is associated with one
    or more logical modules (``module_ids`` -> ``ss.module``). Groups are then
    granted whole modules (``res.mobile.user.group.module_ids``) and may hide
    individual screens/buttons as exceptions
    (``hidden_menu_ids`` / ``hidden_button_ids``).

    Hybrid semantics: a resource **not** associated with any module is treated
    as un-enforced and stays visible to everyone (so newly-synced keys never
    hide existing features). Once a resource belongs to a module it becomes an
    allowlist item — visible only to groups that are granted a module
    containing it AND have not hidden it.

    Inheritance: setting ``implied_group_ids`` does **not** live-inherit UI
    access. Instead the group form's "Copy configuration from implied groups"
    button (``res.mobile.user.group.action_copy_ui_from_implied``) copies the
    implied groups' modules and hidden lists into the group's own fields as a
    one-time snapshot, which the admin then edits. A group's effective UI
    access (``effective_resource_ids``) is resolved from its own config only.
    (Model access and record rules, by contrast, stay live-inherited through
    implied groups.)
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
            granted_keys = group_sudo.effective_resource_ids.mapped("key")
            
        return {"enforced": enforced_keys, "granted": granted_keys}

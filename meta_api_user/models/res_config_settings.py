# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    meta_api_jwt_secret = fields.Char(
        string="JWT Secret",
        config_parameter="meta_api_user.jwt_secret",
        groups="base.group_system",
    )
    meta_api_jwt_algorithm = fields.Selection(
        [
            ("HS256", "HS256"),
            ("HS384", "HS384"),
            ("HS512", "HS512"),
        ],
        string="JWT Algorithm",
        default="HS256",
        config_parameter="meta_api_user.jwt_algorithm",
        groups="base.group_system",
    )
    meta_api_access_token_minutes = fields.Integer(
        string="Access Token Minutes",
        default=15,
        config_parameter="meta_api_user.access_token_minutes",
        groups="base.group_system",
    )
    meta_api_refresh_token_days = fields.Integer(
        string="Refresh Token Days",
        default=30,
        config_parameter="meta_api_user.refresh_token_days",
        groups="base.group_system",
    )
    meta_api_integration_user_id = fields.Many2one(
        "res.users",
        string="Backend Integration User",
        config_parameter="meta_api_user.integration_user_id",
        domain="[('share', '=', False), ('active', '=', True)]",
        groups="base.group_system",
        help="Internal Odoo user used to execute backend ORM operations for mobile API requests.",
    )

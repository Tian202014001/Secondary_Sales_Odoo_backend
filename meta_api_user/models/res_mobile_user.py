# -*- coding: utf-8 -*-

from passlib.context import CryptContext

from odoo import api, fields, models
from odoo.exceptions import AccessDenied, ValidationError


PWD_CONTEXT = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)
MAX_BCRYPT_PASSWORD_BYTES = 72


class ResMobileUser(models.Model):
    _name = "res.mobile.user"
    _description = "Mobile App User"
    _order = "name"

    name = fields.Char(required=True)
    phone = fields.Char(index=True)
    email = fields.Char(index=True)
    password = fields.Char(
        string="Set Password",
        compute="_compute_password",
        inverse="_inverse_password",
        store=False,
        groups="meta_api_user.group_mobile_auth_manager",
        help="Use this field to set or change the password. The plain value is never stored.",
    )
    password_hash = fields.Char(
        required=True,
        readonly=True,
        copy=False,
        groups="base.group_system",
    )
    active = fields.Boolean(default=True)
    is_active = fields.Boolean(related="active", readonly=False, string="Is Active")
    group_id = fields.Many2one(
        "res.mobile.user.group",
        related="employee_id.mobile_user_group_id",
        string="Mobile User Group",
        readonly=False,
        store=True,
    )
    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
    )
    employee_id = fields.Many2one("hr.employee", ondelete="set null")
    last_login = fields.Datetime(readonly=True, copy=False)
    session_ids = fields.One2many("mobile.auth.session", "mobile_user_id")
    session_count = fields.Integer(compute="_compute_session_counts")
    active_session_count = fields.Integer(compute="_compute_session_counts")

    _sql_constraints = [
        ("phone_uniq", "unique(phone)", "The mobile user phone must be unique."),
        ("email_uniq", "unique(email)", "The mobile user email must be unique."),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._normalize_login_values(vals)
            password = vals.pop("password", False)
            if password:
                vals["password_hash"] = self._hash_password(password)
            if not vals.get("password_hash"):
                raise ValidationError("A password is required for mobile users.")
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._normalize_login_values(vals)
        password = vals.pop("password", False)
        if password:
            vals["password_hash"] = self._hash_password(password)
        return super().write(vals)

    @api.constrains("phone", "email")
    def _check_login_identifier(self):
        for user in self:
            if not user.phone and not user.email:
                raise ValidationError("Set at least one login identifier: phone or email.")

    @api.depends("session_ids", "session_ids.is_revoked", "session_ids.refresh_token_expiry")
    def _compute_session_counts(self):
        now = fields.Datetime.now()
        for user in self:
            user.session_count = len(user.session_ids)
            user.active_session_count = len(user.session_ids.filtered(
                lambda session: not session.is_revoked and session.refresh_token_expiry > now
            ))

    def _compute_password(self):
        for user in self:
            user.password = False

    def _inverse_password(self):
        for user in self:
            if user.password:
                user.password_hash = self._hash_password(user.password)

    @api.model
    def _normalize_login_values(self, vals):
        if "phone" in vals:
            vals["phone"] = (vals["phone"] or "").strip() or False
        if "email" in vals:
            vals["email"] = (vals["email"] or "").strip().lower() or False

    @api.model
    def _password_context(self):
        return PWD_CONTEXT

    @api.model
    def _prepare_bcrypt_password(self, password):
        if not password:
            raise ValidationError("Password cannot be empty.")
        if isinstance(password, bytes):
            password_bytes = password
        else:
            password_bytes = str(password).encode("utf-8")
        return password_bytes[:MAX_BCRYPT_PASSWORD_BYTES]

    @api.model
    def _hash_password(self, password):
        return self._password_context().hash(self._prepare_bcrypt_password(password))

    def _verify_password(self, password):
        self.ensure_one()
        if not password or not self.password_hash:
            return False
        return self._password_context().verify(
            self._prepare_bcrypt_password(password),
            self.password_hash,
        )

    def check_password(self, plain_password):
        return self._verify_password(plain_password)

    @api.model
    def authenticate_mobile_user(self, login, password):
        login = (login or "").strip()
        if not login or not password:
            raise AccessDenied()

        normalized_email = login.lower()
        user = self.sudo().search([
            "|",
            ("phone", "=", login),
            ("email", "=", normalized_email),
            ("active", "=", True),
        ], limit=1)

        if not user or not user.check_password(password):
            raise AccessDenied()

        user.sudo().write({"last_login": fields.Datetime.now()})
        return user

    def action_view_sessions(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Mobile Sessions",
            "res_model": "mobile.auth.session",
            "view_mode": "list,form",
            "domain": [("mobile_user_id", "=", self.id)],
            "context": {"default_mobile_user_id": self.id},
        }

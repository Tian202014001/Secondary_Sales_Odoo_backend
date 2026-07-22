# -*- coding: utf-8 -*-

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from odoo import SUPERUSER_ID, api, fields, models
from odoo.exceptions import AccessDenied, UserError, ValidationError
from odoo.osv import expression


class MobileAuthSession(models.Model):
    _name = "mobile.auth.session"
    _description = "Mobile Authentication Session"
    _order = "create_date desc"

    mobile_user_id = fields.Many2one(
        "res.mobile.user",
        required=True,
        ondelete="cascade",
        index=True,
    )
    refresh_token_hash = fields.Char(required=True, readonly=True, copy=False, index=True)
    refresh_token_expiry = fields.Datetime(required=True, readonly=True, copy=False)
    is_revoked = fields.Boolean(default=False, index=True, copy=False)
    revoke_reason = fields.Selection(
        [
            ("logout", "Logged Out"),
            ("admin", "Admin Revoked"),
            ("replaced", "Replaced by New Login"),
        ],
        readonly=True,
        copy=False,
        index=True,
    )
    device_id = fields.Char(copy=False, index=True)
    device_info = fields.Char(copy=False)
    ip_address = fields.Char(copy=False)
    user_agent = fields.Char(copy=False)
    last_used_at = fields.Datetime(readonly=True, copy=False)
    state = fields.Selection(
        [
            ("active", "Active"),
            ("refresh_expired", "Refresh Expired"),
            ("logged_out", "Logged Out"),
            ("revoked", "Revoked"),
        ],
        compute="_compute_state",
        search="_search_state",
    )

    _sql_constraints = [
        (
            "refresh_token_hash_uniq",
            "unique(refresh_token_hash)",
            "The refresh token hash must be unique.",
        ),
    ]

    @api.depends("is_revoked", "revoke_reason", "refresh_token_expiry")
    def _compute_state(self):
        now = fields.Datetime.now()
        for session in self:
            if session.is_revoked and session.revoke_reason == "logout":
                session.state = "logged_out"
            elif session.is_revoked:
                session.state = "revoked"
            elif session.refresh_token_expiry <= now:
                session.state = "refresh_expired"
            else:
                session.state = "active"

    @api.model
    def _search_state(self, operator, value):
        if operator not in ("=", "!="):
            raise NotImplementedError("Only equality state searches are supported.")

        now = fields.Datetime.now()
        domains = {
            "logged_out": [
                ("is_revoked", "=", True),
                ("revoke_reason", "=", "logout"),
            ],
            "revoked": [
                ("is_revoked", "=", True),
                "|",
                ("revoke_reason", "!=", "logout"),
                ("revoke_reason", "=", False),
            ],
            "refresh_expired": [
                ("is_revoked", "=", False),
                ("refresh_token_expiry", "<=", now),
            ],
            "active": [
                ("is_revoked", "=", False),
                ("refresh_token_expiry", ">", now),
            ],
        }
        if value not in domains:
            return [(0, "=", 1)] if operator == "=" else [(1, "=", 1)]

        domain = domains.get(value, [])
        if operator == "!=":
            return expression.distribute_not(["!"] + expression.normalize_domain(domain))
        return domain

    @api.model
    def _get_jwt_secret(self):
        params = self.env["ir.config_parameter"].sudo()
        secret = params.get_param("meta_api_user.jwt_secret")
        if not secret or len(secret.encode("utf-8")) < 32:
            secret = params.get_param("database.secret")
            if not secret or len(secret.encode("utf-8")) < 32:
                secret = "meta_api_secondary_sales_jwt_secret_key_v1_secure_stable_32bytes"
            params.set_param("meta_api_user.jwt_secret", secret)
        return secret


    @api.model
    def _get_jwt_algorithm(self):
        return self.env["ir.config_parameter"].sudo().get_param(
            "meta_api_user.jwt_algorithm",
            "HS256",
        )

    @api.model
    def _get_access_token_minutes(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "meta_api_user.access_token_minutes",
            "15",
        )
        try:
            minutes = int(value or 15)
        except (TypeError, ValueError):
            minutes = 15
        return minutes if minutes > 0 else 15

    @api.model
    def _get_refresh_token_days(self):
        value = self.env["ir.config_parameter"].sudo().get_param(
            "meta_api_user.refresh_token_days",
            "30",
        )
        try:
            days = int(value or 30)
        except (TypeError, ValueError):
            days = 30
        return days if days > 0 else 30

    @api.model
    def _get_integration_user(self):
        user_id = self.env["ir.config_parameter"].sudo().get_param(
            "meta_api_user.integration_user_id"
        )
        if not user_id:
            raise UserError("Configure a Mobile API backend integration user first.")

        try:
            user_id = int(user_id)
        except (TypeError, ValueError) as exc:
            raise UserError("The configured Mobile API backend integration user is invalid.") from exc

        user = self.env["res.users"].sudo().browse(user_id).exists()
        if not user or not user.active:
            raise UserError("The configured Mobile API backend integration user is missing or inactive.")
        if user.share:
            raise UserError("The Mobile API backend integration user must be an internal Odoo user.")
        return user

    @api.model
    def get_integration_env(self, mobile_user=None):
        if mobile_user:
            m_user = mobile_user.sudo()
            if m_user.employee_id and m_user.employee_id.user_id and m_user.employee_id.user_id.active:
                return self.env(user=m_user.employee_id.user_id)
        return self.env(user=self._get_integration_user())

    @api.model
    def get_integration_model(self, model_name, mobile_user=None):
        env = self.get_integration_env(mobile_user=mobile_user)
        return env[model_name]


    @api.model
    def generate_refresh_token(self):
        return secrets.token_urlsafe(48)

    @api.model
    def hash_token(self, token):
        if not token:
            raise ValidationError("Token cannot be empty.")
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    @api.model
    def secure_compare(self, value_1, value_2):
        return hmac.compare_digest(value_1 or "", value_2 or "")

    @api.model
    def create_access_token(self, mobile_user, session=None, access_ttl_minutes=None):
        mobile_user = mobile_user.sudo()
        mobile_user.ensure_one()
        minutes = access_ttl_minutes or self._get_access_token_minutes()
        now = datetime.now(timezone.utc)
        payload = {
            "sub": str(mobile_user.id),
            "mobile_user_id": mobile_user.id,
            "group_id": mobile_user.group_id.id if mobile_user.group_id else False,
            "employee_id": mobile_user.employee_id.id if mobile_user.employee_id else False,
            "company_id": mobile_user.company_id.id if mobile_user.company_id else False,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=minutes)).timestamp()),
            "type": "access",
        }
        if session:
            payload["sid"] = session.id
        token = jwt.encode(payload, self._get_jwt_secret(), algorithm=self._get_jwt_algorithm())
        if isinstance(token, bytes):
            token = token.decode("utf-8")
        return token

    @api.model
    def decode_access_token(self, token):
        try:
            payload = jwt.decode(
                token,
                self._get_jwt_secret(),
                algorithms=[self._get_jwt_algorithm()],
            )
        except ExpiredSignatureError as exc:
            raise AccessDenied("Access token expired.") from exc
        except InvalidTokenError as exc:
            raise AccessDenied("Invalid access token.") from exc

        if payload.get("type") != "access":
            raise AccessDenied("Invalid token type.")
        return payload

    @api.model
    def create_session(
        self,
        mobile_user,
        access_ttl_minutes=None,
        refresh_ttl_days=None,
        device_id=None,
        device_info=None,
        ip_address=None,
        user_agent=None,
    ):
        mobile_user = mobile_user.sudo()
        mobile_user.ensure_one()
        if not mobile_user.active:
            raise AccessDenied()

        device_id = (device_id or "").strip() or False
        if device_id:
            self._revoke_existing_device_sessions(mobile_user, device_id)

        refresh_token = self.generate_refresh_token()
        now = fields.Datetime.now()
        refresh_days = refresh_ttl_days or self._get_refresh_token_days()
        session = self.sudo().create({
            "mobile_user_id": mobile_user.id,
            "refresh_token_hash": self.hash_token(refresh_token),
            "refresh_token_expiry": now + timedelta(days=refresh_days),
            "device_id": device_id,
            "device_info": device_info,
            "ip_address": ip_address,
            "user_agent": user_agent,
        })
        access_token = self.create_access_token(
            mobile_user,
            session=session,
            access_ttl_minutes=access_ttl_minutes,
        )
        return session, access_token, refresh_token

    @api.model
    def login_and_create_session(
        self,
        login,
        password,
        device_id=None,
        device_info=None,
        ip_address=None,
        user_agent=None,
    ):
        """Authenticates credentials and returns access/refresh tokens with user details.

        Returns a dictionary containing:
            - access_token (str): JWT access token.
            - refresh_token (str): Opaque refresh token.
            - token_type (str): "Bearer".
            - expires_in (int): Lifetime of access token in seconds.
            - user (dict): User profile details, including:
                - id (int): Mobile user ID.
                - name (str): Mobile user name.
                - role (str/bool): Mobile user group name.
                - group (dict/bool): Mobile user group details containing id, code, name.
                - employee_id (int/bool): Associated employee ID.
                - employee_name (str/bool): Associated employee name.
            - access (dict): Mobile UI access for the user's group:
                - enforced (list[str]): resource keys currently gated (global).
                - granted (list[str]): keys granted directly to the user's group.
        """
        mobile_user = self.env["res.mobile.user"].authenticate_mobile_user(login, password)
        employee = self._get_mobile_user_employee_payload(mobile_user)
        _session, access_token, refresh_token = self.create_session(
            mobile_user,
            device_id=device_id,
            device_info=device_info,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        group = mobile_user.group_id
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self._get_access_token_minutes() * 60,
            "user": {
                "id": mobile_user.id,
                "name": mobile_user.name,
                "role": group.name if group else False,
                "group": {
                    "id": group.id,
                    "code": group.code,
                    "name": group.name,
                } if group else False,
                "permissions": {
                    "can_view_all_returns": bool(group and group.can_view_all_returns),
                    "can_edit_so_qty": bool(group and group.can_edit_so_qty),
                    "can_edit_qc_qty": bool(group and group.can_edit_qc_qty),
                    "can_edit_effective_qty": bool(group and group.can_edit_effective_qty),
                    "skip_attendance_geolocation": bool(group and getattr(group, "skip_attendance_geolocation", False)),
                } if group else {},
                "employee_id": employee["id"] if employee else False,
                "employee_name": employee["name"] if employee else False,
            },
            "access": self.env["mobile.ui.resource"].get_access_payload(group),
        }

    @api.model
    def _get_mobile_user_employee_payload(self, mobile_user):
        mobile_user = mobile_user.sudo()
        employee_id = mobile_user.employee_id.id
        if not employee_id:
            return False
        employee = (
            self.env["hr.employee"]
            .with_user(SUPERUSER_ID)
            .browse(employee_id)
            .exists()
        )
        if not employee:
            return False
        return {
            "id": employee.id,
            "name": employee.name,
        }

    @api.model
    def validate_access_token(self, raw_token, check_session=False):
        payload = self.decode_access_token(raw_token)
        mobile_user_id = payload.get("mobile_user_id")
        if not mobile_user_id:
            raise AccessDenied("Invalid access token.")

        try:
            mobile_user_id = int(mobile_user_id)
        except (TypeError, ValueError) as exc:
            raise AccessDenied("Invalid access token.") from exc

        mobile_user = self.env["res.mobile.user"].sudo().browse(mobile_user_id).exists()
        if not mobile_user or not mobile_user.active:
            raise AccessDenied()

        session = self.browse()
        session_id = payload.get("sid")
        if session_id:
            try:
                session_id = int(session_id)
            except (TypeError, ValueError) as exc:
                raise AccessDenied("Invalid access token session.") from exc
            session = self.sudo().browse(session_id).exists()
            if session and session.mobile_user_id != mobile_user:
                raise AccessDenied("Invalid access token session.")
            if check_session and (not session or session.is_revoked):
                raise AccessDenied("Session has ended.")
            if session:
                now = fields.Datetime.now()
                if not session.last_used_at or (now - session.last_used_at).total_seconds() > 3600:
                    session.sudo().write({"last_used_at": now})

        return mobile_user, payload, session

    @api.model
    def refresh_session(self, raw_refresh_token, access_ttl_minutes=None, refresh_ttl_days=None):
        token_hash = self.hash_token(raw_refresh_token)
        session = self.sudo().search([
            ("refresh_token_hash", "=", token_hash),
            ("refresh_token_expiry", ">", fields.Datetime.now()),
            ("is_revoked", "=", False),
        ], limit=1)

        if not session or not session.mobile_user_id.active:
            raise AccessDenied()

        access_token = self.create_access_token(
            session.mobile_user_id,
            session=session,
            access_ttl_minutes=access_ttl_minutes,
        )
        refresh_token = self.generate_refresh_token()
        refresh_days = refresh_ttl_days or self._get_refresh_token_days()
        vals = {
            "refresh_token_hash": self.hash_token(refresh_token),
            "refresh_token_expiry": fields.Datetime.now() + timedelta(days=refresh_days),
            "last_used_at": fields.Datetime.now(),
        }

        session.sudo().write(vals)
        return session, access_token, refresh_token

    @api.model
    def refresh_session_response(
        self,
        raw_refresh_token,
        access_ttl_minutes=None,
        refresh_ttl_days=None,
    ):
        _session, access_token, refresh_token = self.refresh_session(
            raw_refresh_token,
            access_ttl_minutes=access_ttl_minutes,
            refresh_ttl_days=refresh_ttl_days,
        )
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": (access_ttl_minutes or self._get_access_token_minutes()) * 60,
        }

    @api.model
    def get_dashboard_data(self):
        MobileUser = self.env["res.mobile.user"].sudo().with_context(active_test=False)
        Group = self.env["res.mobile.user.group"].sudo().with_context(active_test=False)
        Session = self.sudo()
        now = fields.Datetime.now()
        now_string = fields.Datetime.to_string(now)

        recent_sessions = Session.search_read(
            [],
            [
                "mobile_user_id",
                "state",
                "revoke_reason",
                "device_id",
                "device_info",
                "ip_address",
                "last_used_at",
                "refresh_token_expiry",
                "is_revoked",
            ],
            limit=8,
            order="create_date desc",
        )

        stats = {
            "total_users": MobileUser.search_count([]),
            "active_users": MobileUser.search_count([("active", "=", True)]),
            "inactive_users": MobileUser.search_count([("active", "=", False)]),
            "groups": Group.search_count([]),
            "roles": Group.search_count([]),
            "sessions": Session.search_count([]),
            "active_sessions": Session.search_count([
                ("is_revoked", "=", False),
                ("refresh_token_expiry", ">", now),
            ]),
            "logged_out_sessions": Session.search_count([
                ("is_revoked", "=", True),
                ("revoke_reason", "=", "logout"),
            ]),
            "revoked_sessions": Session.search_count([
                ("is_revoked", "=", True),
                "|",
                ("revoke_reason", "!=", "logout"),
                ("revoke_reason", "=", False),
            ]),
            "expired_sessions": Session.search_count([
                ("is_revoked", "=", False),
                ("refresh_token_expiry", "<=", now),
            ]),
        }
        integration_user_id = self.env["ir.config_parameter"].sudo().get_param(
            "meta_api_user.integration_user_id"
        )
        integration_user = self.env["res.users"].sudo()
        if integration_user_id:
            try:
                integration_user = integration_user.browse(int(integration_user_id)).exists()
            except (TypeError, ValueError):
                integration_user = self.env["res.users"].sudo()

        return {
            "stats": stats,
            "settings": {
                "access_token_minutes": self._get_access_token_minutes(),
                "refresh_token_days": self._get_refresh_token_days(),
                "jwt_algorithm": self._get_jwt_algorithm(),
                "has_jwt_secret": bool(
                    self.env["ir.config_parameter"].sudo().get_param("meta_api_user.jwt_secret")
                ),
                "integration_user": integration_user.name if integration_user else False,
                "has_integration_user": bool(integration_user),
            },
            "recent_sessions": recent_sessions,
            "actions": {
                "users": {
                    "model": "res.mobile.user",
                    "domain": [],
                    "name": "Mobile Users",
                    "context": {"active_test": False},
                },
                "active_users": {
                    "model": "res.mobile.user",
                    "domain": [("active", "=", True)],
                    "name": "Active Mobile Users",
                    "context": {"active_test": False},
                },
                "inactive_users": {
                    "model": "res.mobile.user",
                    "domain": [("active", "=", False)],
                    "name": "Inactive Mobile Users",
                    "context": {"active_test": False},
                },
                "sessions": {
                    "model": "mobile.auth.session",
                    "domain": [],
                    "name": "Mobile Sessions",
                },
                "active_sessions": {
                    "model": "mobile.auth.session",
                    "domain": [
                        ("is_revoked", "=", False),
                        ("refresh_token_expiry", ">", now_string),
                    ],
                    "name": "Active Mobile Sessions",
                },
                "revoked_sessions": {
                    "model": "mobile.auth.session",
                    "domain": [
                        ("is_revoked", "=", True),
                        "|",
                        ("revoke_reason", "!=", "logout"),
                        ("revoke_reason", "=", False),
                    ],
                    "name": "Revoked Mobile Sessions",
                },
                "logged_out_sessions": {
                    "model": "mobile.auth.session",
                    "domain": [
                        ("is_revoked", "=", True),
                        ("revoke_reason", "=", "logout"),
                    ],
                    "name": "Logged Out Mobile Sessions",
                },
                "expired_sessions": {
                    "model": "mobile.auth.session",
                    "domain": [
                        ("is_revoked", "=", False),
                        ("refresh_token_expiry", "<=", now_string),
                    ],
                    "name": "Expired Mobile Sessions",
                },
                "groups": {
                    "model": "res.mobile.user.group",
                    "domain": [],
                    "name": "Mobile User Groups",
                    "context": {"active_test": False},
                },
                "roles": {
                    "model": "res.mobile.user.group",
                    "domain": [],
                    "name": "Mobile User Groups",
                    "context": {"active_test": False},
                },
            },
        }

    def action_revoke(self):
        self.write({
            "is_revoked": True,
            "revoke_reason": "admin",
        })

    def action_replaced(self):
        self.write({
            "is_revoked": True,
            "revoke_reason": "replaced",
            "last_used_at": fields.Datetime.now(),
        })

    def action_logout(self):
        self.write({
            "is_revoked": True,
            "revoke_reason": "logout",
            "last_used_at": fields.Datetime.now(),
        })

    @api.model
    def _revoke_existing_device_sessions(self, mobile_user, device_id):
        sessions = self.sudo().search([
            ("mobile_user_id", "=", mobile_user.id),
            ("device_id", "=", device_id),
            ("is_revoked", "=", False),
        ])
        if sessions:
            sessions.action_replaced()

    def unlink(self):
        if not self.env.user.has_group("base.group_system"):
            raise AccessDenied()
        return super().unlink()

# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        """Relabel chatter authored during a mobile-API request.

        The mobile app acts through an API context. During an API request
        ``meta_ss_rest_api`` injects ``mobile_api_user_id`` into the context;
        we use it to resolve the real acting user/employee. If the mobile user is
        linked to an internal user, we attribute the chatter to the internal
        user's partner (``user.partner_id``). Otherwise, we fall back to a combined
        text label, e.g. ``Mobile API User (Abigail Peterson)``.
        """
        try:
            self._ss_apply_api_attribution(vals_list)
        except Exception:  # pragma: no cover - attribution must never block a create
            _logger.exception("meta_ss_chatter_attribution: failed to relabel message author")
        return super().create(vals_list)

    def _ss_apply_api_attribution(self, vals_list):
        """Rewrite the author of integration-user messages to the acting user partner or employee label."""
        mobile_user_id = self.env.context.get("mobile_api_user_id")
        if not mobile_user_id:
            return

        mobile_user = self.env["res.mobile.user"].sudo().browse(mobile_user_id)
        if not mobile_user.exists():
            return

        # 1. Prefer internal user's partner ID if available
        user_partner = False
        if mobile_user.employee_id and mobile_user.employee_id.user_id and mobile_user.employee_id.user_id.partner_id:
            user_partner = mobile_user.employee_id.user_id.partner_id

        label = self._ss_api_author_label(mobile_user)

        # Build set of integration/system partner IDs to replace
        integration_partner_ids = {self.env.user.partner_id.id}
        param = self.env["ir.config_parameter"].sudo().get_param("meta_api_user.integration_user_id")
        if param:
            try:
                config_user = self.env["res.users"].sudo().browse(int(param))
                if config_user.exists() and config_user.partner_id:
                    integration_partner_ids.add(config_user.partner_id.id)
            except (TypeError, ValueError):
                pass

        for vals in vals_list:
            author_id = vals.get("author_id")
            # Relabel if author is empty or matches integration/system user
            if not author_id or author_id in integration_partner_ids:
                if user_partner:
                    vals["author_id"] = user_partner.id
                    vals["email_from"] = user_partner.email_formatted or user_partner.name
                else:
                    vals["author_id"] = False
                    if label:
                        vals["email_from"] = label

    @api.model
    def _ss_api_author_label(self, mobile_user):
        """Build the chatter author label for a mobile-API request."""
        if not mobile_user or not mobile_user.exists():
            return False

        actor = self._ss_api_actor_name()
        subject = (mobile_user.employee_id and mobile_user.employee_id.name) or mobile_user.name
        if not subject:
            return False
        return "%s (%s)" % (actor, subject)

    @api.model
    def _ss_api_actor_name(self):
        """Display name of the mobile-API integration user."""
        param = self.env["ir.config_parameter"].sudo().get_param(
            "meta_api_user.integration_user_id"
        )
        if param:
            try:
                user = self.env["res.users"].sudo().browse(int(param))
            except (TypeError, ValueError):
                user = self.env["res.users"]
            if user.exists():
                return user.name
        if self.env.uid != SUPERUSER_ID:
            return self.env.user.name
        return "Mobile App"

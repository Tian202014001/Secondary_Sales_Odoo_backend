# -*- coding: utf-8 -*-
import logging

from odoo import SUPERUSER_ID, api, models

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    @api.model_create_multi
    def create(self, vals_list):
        """Relabel chatter authored during a mobile-API request.

        The whole mobile app acts through a single integration user, so every
        chatter/log entry it produces is attributed to that user. During an API
        request ``meta_ss_rest_api`` injects ``mobile_api_user_id`` into the
        context (see ``utils/common.py:get_mobile_api_context``); we use it to
        resolve the real acting employee and render the author as a combined
        label, e.g. ``meta_api_user (Abigail Peterson)``.

        Rendering as a text label (author_id=False + email_from) keeps the real
        actor audited internally while showing who acted, and leaves all normal
        web/backend traffic untouched (the context key is absent there).

        This method runs on *every* chatter message create, so attribution is
        wrapped defensively: any failure is logged and swallowed so it can never
        block the creation of the underlying record.
        """
        try:
            self._ss_apply_api_attribution(vals_list)
        except Exception:  # pragma: no cover - attribution must never block a create
            _logger.exception("meta_ss_chatter_attribution: failed to relabel message author")
        return super().create(vals_list)

    def _ss_apply_api_attribution(self, vals_list):
        """Rewrite the author of integration-user messages to the acting-employee label."""
        mobile_user_id = self.env.context.get("mobile_api_user_id")
        if not mobile_user_id:
            return

        label = self._ss_api_author_label(mobile_user_id)
        if not label:
            return

        integration_partner_id = self.env.user.partner_id.id
        for vals in vals_list:
            # Only relabel messages that would otherwise be attributed to the
            # integration user; leave genuine third-party authors alone.
            author_id = vals.get("author_id")
            if not author_id or author_id == integration_partner_id:
                vals["author_id"] = False
                vals["email_from"] = label

    @api.model
    def _ss_api_author_label(self, mobile_user_id):
        """Build the chatter author label for a mobile-API request.

        Returns ``"<integration user> (<employee or mobile user name>)"`` or
        ``False`` when the mobile user cannot be resolved (message untouched).
        """
        mobile_user = self.env["res.mobile.user"].sudo().browse(mobile_user_id)
        if not mobile_user.exists():
            return False

        actor = self._ss_api_actor_name()
        subject = mobile_user.employee_id.name or mobile_user.name
        if not subject:
            return False
        return "%s (%s)" % (actor, subject)

    @api.model
    def _ss_api_actor_name(self):
        """Display name of the mobile-API integration user.

        Records may be created via ``sudo()`` (e.g. stock transfers), in which
        case ``self.env.user`` is SUPERUSER and unusable for the label. Resolve
        the configured integration user so the label stays stable regardless of
        who the ORM is currently running as.
        """
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

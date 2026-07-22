# -*- coding: utf-8 -*-

import json

from odoo import fields, http
from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    format_date,
    get_mobile_api_context,
    mobile_api_error_boundary,
)

# Cap so a caller can never pull the whole table in one request.
MAX_LIMIT = 50
DEFAULT_LIMIT = 20


class MobileNotificationController(http.Controller):
    """Consumer endpoints for the in-app notification center.

    Every query is scoped to the authenticated mobile user (the JWT identity resolved by
    ``get_mobile_api_context``), so a user only ever sees or mutates their own rows.
    """

    @http.route(f"{API_PREFIX}/mobile/notifications", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def list_notifications(self, **payload):
        """Return the caller's notifications (newest first) plus the unread count."""
        mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=False)
        Notification = api_env['mobile.push.notification'].sudo()

        limit = max(1, min(self._as_int(payload.get('limit'), DEFAULT_LIMIT), MAX_LIMIT))
        offset = max(0, self._as_int(payload.get('offset'), 0))

        domain = [('mobile_user_id', '=', mobile_user.id)]
        if payload.get('only_unread'):
            domain.append(('is_read', '=', False))

        type_labels = dict(Notification._fields['notification_type'].selection)
        records = Notification.search(domain, order='create_date desc', limit=limit, offset=offset)

        return {
            "success": True,
            "api_version": API_VERSION,
            "data": {
                "notifications": [self._serialize(notif, type_labels) for notif in records],
                "unread_count": self._unread_count(Notification, mobile_user),
                "total": Notification.search_count(domain),
            },
        }

    @http.route(f"{API_PREFIX}/mobile/notifications/unread-count", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def unread_count(self, **payload):
        """Lightweight endpoint for the bell badge."""
        mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=False)
        Notification = api_env['mobile.push.notification'].sudo()
        return {
            "success": True,
            "api_version": API_VERSION,
            "data": {"unread_count": self._unread_count(Notification, mobile_user)},
        }

    @http.route(f"{API_PREFIX}/mobile/notifications/mark-read", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def mark_read(self, **payload):
        """Mark the given notification ids read; returns the updated unread count."""
        mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=False)

        ids = payload.get('notification_ids')
        if not ids and payload.get('notification_id') is not None:
            ids = [payload.get('notification_id')]
        if not ids:
            return error_response("validation_error", "notification_ids is required.")
        try:
            ids = [int(i) for i in ids]
        except (ValueError, TypeError):
            return error_response("validation_error", "notification_ids must be integers.")

        Notification = api_env['mobile.push.notification'].sudo()
        notifs = Notification.search([
            ('id', 'in', ids),
            ('mobile_user_id', '=', mobile_user.id),
            ('is_read', '=', False),
        ])
        if notifs:
            notifs.write({'is_read': True, 'read_at': fields.Datetime.now()})

        return {
            "success": True,
            "api_version": API_VERSION,
            "data": {"unread_count": self._unread_count(Notification, mobile_user)},
        }

    @http.route(f"{API_PREFIX}/mobile/notifications/mark-all-read", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def mark_all_read(self, **payload):
        """Mark every unread notification of the caller as read."""
        mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=False)
        Notification = api_env['mobile.push.notification'].sudo()
        notifs = Notification.search([
            ('mobile_user_id', '=', mobile_user.id),
            ('is_read', '=', False),
        ])
        if notifs:
            notifs.write({'is_read': True, 'read_at': fields.Datetime.now()})

        return {
            "success": True,
            "api_version": API_VERSION,
            "data": {"unread_count": 0},
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _as_int(value, default=0):
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _unread_count(Notification, mobile_user):
        return Notification.search_count([
            ('mobile_user_id', '=', mobile_user.id),
            ('is_read', '=', False),
        ])

    def _serialize(self, notif, type_labels):
        return {
            "id": notif.id,
            "type": notif.notification_type,
            "type_label": type_labels.get(notif.notification_type, notif.notification_type),
            "title": notif.title,
            "body": notif.body,
            "is_read": notif.is_read,
            "created_at": format_date(notif.create_date),
            "link": self._serialize_link(notif),
        }

    @staticmethod
    def _serialize_link(notif):
        """Generic record reference for deep-linking, or None when there is none."""
        if not notif.res_model or not notif.res_id:
            return None

        payload = {}
        if notif.payload_json:
            try:
                payload = json.loads(notif.payload_json)
            except (ValueError, TypeError):
                payload = {}

        sale_type = None
        if notif.res_model == 'sale.order' and notif.sale_order_id:
            sale_type = notif.sale_order_id.sale_type or None

        return {
            "model": notif.res_model,
            "id": notif.res_id,
            "name": payload.get('name'),
            "sale_type": sale_type,
            "action_link": payload.get('action_link'),
        }

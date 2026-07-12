# -*- coding: utf-8 -*-

from odoo import http, fields
from odoo.http import request
from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    mobile_api_error_boundary,
    handle_api_exception,
)


class MobileDeviceController(http.Controller):

    @http.route(f"{API_PREFIX}/mobile/device/register", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def register_device(self, **payload):
        """Register or update an FCM token for the mobile user."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=False)

        fcm_token = payload.get('fcm_token')
        platform = payload.get('platform')

        if not fcm_token or not platform:
            return error_response("validation_error", "fcm_token and platform are required.")
        if platform not in {'android', 'ios', 'web'}:
            return error_response("validation_error", "platform must be one of: android, ios, web.")

        Device = api_env['res.mobile.device'].sudo()

        # Check if token exists
        existing_device = Device.search([('fcm_token', '=', fcm_token)], limit=1)

        vals = {
            'mobile_user_id': _mobile_user.id,
            'employee_id': _mobile_user.employee_id.id if _mobile_user.employee_id else False,
            'platform': platform,
            'device_name': payload.get('device_name'),
            'app_version': payload.get('app_version'),
            'active': True,
            'last_seen_at': fields.Datetime.now(),
        }

        if existing_device:
            existing_device.write(vals)
        else:
            vals['fcm_token'] = fcm_token
            Device.create(vals)

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Device registered successfully.",
        }

    @http.route(f"{API_PREFIX}/mobile/device/unregister", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def unregister_device(self, **payload):
        """Deactivate an FCM token."""
        _mobile_user, api_env, payload = get_mobile_api_context(payload, require_employee=False)

        fcm_token = payload.get('fcm_token')
        if not fcm_token:
            return error_response("validation_error", "fcm_token is required.")

        Device = api_env['res.mobile.device'].sudo()
        devices = Device.search([('fcm_token', '=', fcm_token), ('mobile_user_id', '=', _mobile_user.id)])
        devices.write({'active': False})

        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Device unregistered successfully.",
        }


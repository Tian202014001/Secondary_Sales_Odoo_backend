# -*- coding: utf-8 -*-

import json
import logging
from odoo import models, api, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
except ImportError:
    firebase_admin = None
    messaging = None


class MobileNotificationService(models.AbstractModel):
    _name = 'mobile.notification.service'
    _description = 'Mobile Notification Service'

    def _get_firebase_app(self):
        """Initialize and return the Firebase Admin SDK app."""
        if not firebase_admin:
            raise UserError("firebase-admin python package is not installed.")

        # Get service account path from system parameters
        service_account_path = self.env['ir.config_parameter'].sudo().get_param('firebase.service_account_path')
        if service_account_path:
            service_account_path = service_account_path.strip()
        if not service_account_path:
            raise UserError("System parameter 'firebase.service_account_path' is not set.")

        try:
            # Check if default app is already initialized
            app = firebase_admin.get_app()
            return app
        except ValueError:
            # Initialize new app
            cred = credentials.Certificate(service_account_path)
            return firebase_admin.initialize_app(cred)

    @api.model
    def process_pending_notifications(self):
        """Cron job entry point to process pending push notifications."""
        notifications = self.env['mobile.push.notification'].search([
            ('state', 'in', ['pending', 'failed']),
        ], limit=50)

        if not notifications:
            return

        try:
            self._get_firebase_app()
        except Exception as e:
            _logger.error("Failed to initialize Firebase Admin SDK: %s", e)
            return

        for notif in notifications:
            self._send_notification(notif)

    def _send_notification(self, notif):
        """Send a single notification to unsent active devices of the user."""
        devices = self.env['res.mobile.device'].search([
            ('mobile_user_id', '=', notif.mobile_user_id.id),
            ('active', '=', True),
            ('id', 'not in', notif.sent_device_ids.ids),
        ])

        if not devices:
            if notif.sent_device_ids:
                notif.write({
                    'state': 'sent',
                    'sent_at': notif.sent_at or fields.Datetime.now(),
                    'error_message': False,
                })
                return
            notif.write({
                'state': 'cancelled',
                'error_message': 'No active devices found for user.'
            })
            return

        # Prepare payload
        data_payload = {}
        if notif.payload_json:
            try:
                data_payload = json.loads(notif.payload_json)
                # Firebase data payload values must be strings
                data_payload = {str(k): str(v) for k, v in data_payload.items()}
            except Exception as e:
                _logger.warning("Invalid payload_json on notification %s: %s", notif.id, e)

        tokens = devices.mapped('fcm_token')
        
        # Create multicast message
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title=notif.title,
                body=notif.body,
            ),
            data=data_payload,
            tokens=tokens,
        )

        try:
            response = messaging.send_each_for_multicast(message)

            # Handle response
            if response.failure_count > 0:
                errors = []
                retryable_errors = []
                sent_device_ids = []
                invalid_devices = self.env['res.mobile.device']
                for idx, resp in enumerate(response.responses):
                    device = devices[idx]
                    if resp.success:
                        sent_device_ids.append(device.id)
                        continue

                    error_msg = str(resp.exception)
                    errors.append(f"Token {tokens[idx]}: {error_msg}")

                    # Deactivate invalid tokens
                    if self._is_permanent_token_error(error_msg):
                        invalid_devices |= device
                    else:
                        retryable_errors.append(error_msg)

                if invalid_devices:
                    invalid_devices.write({'active': False})

                vals = {
                    'error_message': '\n'.join(errors),
                    'sent_at': fields.Datetime.now() if response.success_count else False,
                }
                if sent_device_ids:
                    vals['sent_device_ids'] = [(4, device_id) for device_id in sent_device_ids]

                if retryable_errors:
                    state = 'failed'
                elif response.success_count:
                    state = 'sent'
                else:
                    state = 'cancelled'

                vals.update({
                    'state': state,
                    'retry_count': notif.retry_count + 1 if retryable_errors else notif.retry_count,
                })
                notif.write({
                    key: value
                    for key, value in vals.items()
                    if value is not False or key in {'sent_at', 'error_message'}
                })
            else:
                notif.write({
                    'state': 'sent',
                    'sent_at': fields.Datetime.now(),
                    'error_message': False,
                    'sent_device_ids': [(4, device.id) for device in devices],
                })

        except Exception as e:
            _logger.exception("Failed to send Firebase multicast message.")
            notif.write({
                'state': 'failed',
                'error_message': str(e),
                'retry_count': notif.retry_count + 1,
            })

    def _is_permanent_token_error(self, error_msg):
        return (
            "not a valid FCM registration token" in error_msg
            or "Requested entity was not found" in error_msg
            or "registration-token-not-registered" in error_msg
            or "UNREGISTERED" in error_msg
            or "INVALID_ARGUMENT" in error_msg
        )

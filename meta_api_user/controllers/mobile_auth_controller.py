# -*- coding: utf-8 -*-

import json
import logging

from werkzeug.exceptions import BadRequest

from odoo import http
from odoo.exceptions import AccessDenied, UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class MobileAuthController(http.Controller):
    def _json_response(self, payload, status=200):
        return request.make_response(
            json.dumps(payload, default=str),
            headers=[
                ("Content-Type", "application/json"),
                ("Cache-Control", "no-store"),
            ],
            status=status,
        )

    def _parse_json_payload(self):
        if not request.httprequest.is_json:
            raise BadRequest("Request body must be JSON.")

        payload = request.httprequest.get_json(silent=True)
        if not isinstance(payload, dict):
            raise BadRequest("Invalid JSON body.")
        return payload

    def _bearer_token(self):
        authorization = request.httprequest.headers.get("Authorization", "")
        parts = authorization.strip().split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
            raise AccessDenied("Missing bearer token.")
        return parts[1].strip()

    def _client_ip(self):
        forwarded_for = request.httprequest.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",", 1)[0].strip()
        return request.httprequest.remote_addr

    def _user_agent(self):
        return request.httprequest.headers.get("User-Agent")

    def _handle_bad_request(self, exc):
        return self._json_response({
            "error": "bad_request",
            "message": str(exc.description if hasattr(exc, "description") else exc),
        }, status=400)

    def _handle_access_denied(self):
        return self._json_response({
            "error": "unauthorized",
            "message": "Invalid or expired mobile credentials.",
        }, status=401)

    def _handle_validation_error(self, exc):
        return self._json_response({
            "error": "validation_error",
            "message": str(exc),
        }, status=400)

    def _handle_unexpected_error(self):
        _logger.exception("Unexpected mobile authentication API error")
        return self._json_response({
            "error": "server_error",
            "message": "An unexpected server error occurred.",
        }, status=500)

    @http.route(
        "/api/v1/auth/login",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def login(self):
        try:
            payload = self._parse_json_payload()
            login = payload.get("login")
            password = payload.get("password")

            if not login or not password:
                raise BadRequest("Both 'login' and 'password' are required.")

            data = request.env["mobile.auth.session"].sudo().login_and_create_session(
                login=login,
                password=password,
                device_id=payload.get("device_id"),
                device_info=payload.get("device_info"),
                ip_address=self._client_ip(),
                user_agent=self._user_agent(),
            )
            return self._json_response(data)
        except BadRequest as exc:
            return self._handle_bad_request(exc)
        except AccessDenied:
            return self._handle_access_denied()
        except (UserError, ValidationError) as exc:
            return self._handle_validation_error(exc)
        except Exception:
            return self._handle_unexpected_error()

    @http.route(
        "/api/v1/auth/refresh",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def refresh(self):
        try:
            payload = self._parse_json_payload()
            refresh_token = payload.get("refresh_token")
            if not refresh_token:
                raise BadRequest("'refresh_token' is required.")

            data = request.env["mobile.auth.session"].sudo().refresh_session_response(refresh_token)
            return self._json_response(data)
        except BadRequest as exc:
            return self._handle_bad_request(exc)
        except AccessDenied:
            return self._handle_access_denied()
        except (UserError, ValidationError) as exc:
            return self._handle_validation_error(exc)
        except Exception:
            return self._handle_unexpected_error()

    @http.route(
        "/api/v1/auth/logout",
        type="http",
        auth="none",
        methods=["POST"],
        csrf=False,
    )
    def logout(self):
        try:
            token = self._bearer_token()
            _mobile_user, _payload, session = (
                request.env["mobile.auth.session"].sudo().validate_access_token(
                    token,
                    check_session=False,
                )
            )
            if not session:
                raise AccessDenied("No session found for token.")

            session.sudo().action_logout()
            return self._json_response({
                "success": True,
                "message": "Logged out successfully.",
            })
        except BadRequest as exc:
            return self._handle_bad_request(exc)
        except AccessDenied:
            return self._handle_access_denied()
        except (UserError, ValidationError) as exc:
            return self._handle_validation_error(exc)
        except Exception:
            return self._handle_unexpected_error()

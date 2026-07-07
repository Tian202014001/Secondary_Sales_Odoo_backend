# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessDenied, ValidationError

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    get_mobile_api_context,
    handle_api_exception,
)

VALID_RES_TYPES = ("screen", "action")


class AccessControlController(http.Controller):
    """Endpoints for the app's screen/action access control.

    See ACCESS_CONTROL_PLAN.md in the Flutter repo. The app owns the resource
    key catalog and syncs it here; admins grant keys to mobile groups; the app
    reads its allow-set from the login ``access`` block or from
    ``/access/permissions``.
    """

    @http.route(f"{API_PREFIX}/access/permissions", type="json", auth="user", methods=["POST"])
    def get_permissions(self, **payload):
        try:
            mobile_user, api_env, _payload = get_mobile_api_context(payload)
            group = mobile_user.sudo().group_id
            access = api_env["mobile.ui.resource"].sudo().get_access_payload(group)
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Access permissions loaded.",
                "data": access,
            }
        except Exception as exc:
            return handle_api_exception(exc)

    @http.route(f"{API_PREFIX}/access/catalog/sync", type="json", auth="user", methods=["POST"])
    def sync_catalog(self, **payload):
        try:
            mobile_user, api_env, payload = get_mobile_api_context(payload)

            # Gate: only groups explicitly allowed may mutate the catalog.
            group = mobile_user.sudo().group_id
            if not group or not group.can_manage_access:
                raise AccessDenied("You are not allowed to manage the access catalog.")

            resources = payload.get("resources")
            if not isinstance(resources, list) or not resources:
                raise ValidationError("'resources' must be a non-empty list.")

            app_version = (payload.get("app_version") or "").strip()
            # active_test=False so a previously-removed key can be reactivated.
            Resource = api_env["mobile.ui.resource"].sudo().with_context(active_test=False)

            seen_keys = []
            added = 0
            updated = 0
            for item in resources:
                if not isinstance(item, dict):
                    continue
                key = (item.get("key") or "").strip()
                if not key:
                    continue
                res_type = item.get("type") or "screen"
                if res_type not in VALID_RES_TYPES:
                    raise ValidationError(
                        "Invalid resource type '%s' for key '%s'." % (res_type, key)
                    )
                vals = {
                    "res_type": res_type,
                    "module": (item.get("module") or "").strip(),
                    "label": (item.get("label") or key).strip(),
                    "active": True,
                    "last_seen": app_version,
                }
                existing = Resource.search([("key", "=", key)], limit=1)
                if existing:
                    existing.write(vals)
                    updated += 1
                else:
                    Resource.create(dict(vals, key=key))
                    added += 1
                seen_keys.append(key)

            # Keys the app no longer ships are archived (grants are preserved).
            stale = Resource.search([("key", "not in", seen_keys), ("active", "=", True)])
            deactivated = len(stale)
            if stale:
                stale.write({"active": False})

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Catalog synced.",
                "data": {
                    "added": added,
                    "updated": updated,
                    "deactivated": deactivated,
                    "total": len(seen_keys),
                },
            }
        except Exception as exc:
            return handle_api_exception(exc)

# -*- coding: utf-8 -*-

from odoo import http
from odoo.exceptions import AccessDenied, ValidationError

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    get_mobile_api_context,
    mobile_api_error_boundary,
)

VALID_RES_TYPES = ("screen", "action")


def _clean_string_list(value):
    if not isinstance(value, list):
        return []
    cleaned = []
    for item in value:
        text = (item or "").strip() if isinstance(item, str) else ""
        if text and text not in cleaned:
            cleaned.append(text)
    return cleaned


class AccessControlController(http.Controller):
    """Endpoints for the app's screen/action access control.

    See ACCESS_CONTROL_PLAN.md in the Flutter repo. The app owns the resource
    key catalog and syncs it here; admins grant keys to mobile groups; the app
    reads its allow-set from the login ``access`` block or from
    ``/access/permissions``.
    """

    @http.route(f"{API_PREFIX}/access/permissions", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_permissions(self, **payload):
        mobile_user, api_env, _payload = get_mobile_api_context(payload)
        group = mobile_user.sudo().group_id
        access = api_env["mobile.ui.resource"].sudo().get_access_payload(group)
        return {
            "success": True,
            "api_version": API_VERSION,
            "message": "Access permissions loaded.",
            "data": access,
        }

    @http.route(f"{API_PREFIX}/access/catalog/sync", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def sync_catalog(self, **payload):
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
        Module = api_env["ss.module"].sudo()

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

            if "ss_module_codes" in item:
                module_codes = _clean_string_list(item.get("ss_module_codes"))
                modules = Module.browse()
                if module_codes:
                    modules = Module.search([("code", "in", module_codes), ("active", "=", True)])
                    found_codes = set(modules.mapped("code"))
                    missing_codes = sorted(set(module_codes) - found_codes)
                    if missing_codes:
                        raise ValidationError(
                            "Unknown ss.module code(s) for key '%s': %s"
                            % (key, ", ".join(missing_codes))
                        )
                vals["module_ids"] = [(6, 0, modules.ids)]

            existing = Resource.search([("key", "=", key)], limit=1)
            if existing:
                resource = existing
                resource.write(vals)
                updated += 1
            else:
                resource = Resource.create(dict(vals, key=key))
                added += 1

            legacy_keys = _clean_string_list(item.get("legacy_keys"))
            if legacy_keys:
                self._copy_legacy_hidden_links(api_env, resource, legacy_keys)
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

    def _copy_legacy_hidden_links(self, api_env, resource, legacy_keys):
        legacy_resources = api_env["mobile.ui.resource"].sudo().with_context(
            active_test=False
        ).search([
            ("key", "in", legacy_keys),
            ("id", "!=", resource.id),
        ])
        if not legacy_resources:
            return

        table = (
            "res_mobile_user_group_hidden_menu_rel"
            if resource.res_type == "screen"
            else "res_mobile_user_group_hidden_button_rel"
        )
        api_env.cr.execute(
            f"""
            INSERT INTO {table} (group_id, resource_id)
            SELECT DISTINCT src.group_id, %s
              FROM {table} src
             WHERE src.resource_id = ANY(%s)
               AND NOT EXISTS (
                   SELECT 1
                     FROM {table} dst
                    WHERE dst.group_id = src.group_id
                      AND dst.resource_id = %s
               )
            """,
            [resource.id, legacy_resources.ids, resource.id],
        )


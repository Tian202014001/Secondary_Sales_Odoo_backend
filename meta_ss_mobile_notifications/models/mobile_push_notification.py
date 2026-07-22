# -*- coding: utf-8 -*-

import json

from odoo import api, fields, models


class MobilePushNotification(models.Model):
    _inherit = 'mobile.push.notification'

    is_read = fields.Boolean(default=False, index=True)
    read_at = fields.Datetime()

    # Generic record reference (the mail.message / mail.activity idiom) so a notification
    # can point at any record, not just a sale order. Derived from payload_json, which the
    # base module's mixin already populates for every notification.
    res_model = fields.Char(string='Related Model', index=True)
    res_id = fields.Integer(string='Related Record ID', index=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._apply_record_reference(vals)
        return super().create(vals_list)

    def _apply_record_reference(self, vals):
        """Fill res_model/res_id in-place from payload_json.

        The base module's mixin stamps model/id/name into payload_json for every
        notification, so the generic reference can be derived here without touching it.
        """
        model = vals.get('res_model')
        rec_id = vals.get('res_id')
        if model and rec_id:
            return

        payload = vals.get('payload_json')
        if payload and (not model or not rec_id):
            try:
                data = json.loads(payload)
            except (ValueError, TypeError):
                data = {}
            model = model or data.get('model')
            rec_id = rec_id or data.get('id')

        if model:
            vals['res_model'] = model
        if rec_id:
            try:
                vals['res_id'] = int(rec_id)
            except (ValueError, TypeError):
                pass

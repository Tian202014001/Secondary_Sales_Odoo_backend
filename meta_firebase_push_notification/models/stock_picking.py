# -*- coding: utf-8 -*-

import json
import logging

from odoo import api, fields, models


_logger = logging.getLogger(__name__)


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        res = super().button_validate()
        
        # Check if the picking belongs to a sale order and has a mobile user associated with the order creator
        for picking in self:
            if picking.sale_id and picking.sale_id.mobile_user_id and picking.state == 'done':
                # Trigger notification for delivery validated
                _logger.info("Triggering Delivery Order Validated notification for Order %s to user %s", picking.sale_id.name, picking.sale_id.mobile_user_id.name)
                
                title = 'Delivery Order Validated'
                body = f"Order #{picking.sale_id.name} has been validated for delivery by Supply Chain."
                
                picking.sale_id._create_mobile_notification(
                    notification_type='delivery_order_validated',
                    title=title,
                    body=body,
                    target_user=picking.sale_id.mobile_user_id,
                )
                
        return res

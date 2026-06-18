# -*- coding: utf-8 -*-

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = "sale.order"

    sale_type = fields.Selection(
        selection=[
            ('primary', 'Primary'),
            ('secondary', 'Secondary'),
        ],
        string="Sale Type"
    )

    so_employee_id = fields.Many2one(
        'hr.employee',
        string="Sales Employee",
        help="Employee responsible for this sales order"
    )

    route_id = fields.Many2one(
        'sale.route',
        string="Route",
        domain="[('active', '=', True)]",
        help="Route associated with this sales order"
    )

    visit_id = fields.Many2one(
        'outlet.visit',
        string="Visit",
        domain="[('outlet_id', '=', partner_id)]",
        help="Outlet visit associated with this sales order"
    )

    @api.onchange("so_employee_id")
    def _onchange_so_employee_id(self):
        if (
            self.route_id
            and self.route_id.ss_employee_id
            and self.so_employee_id != self.route_id.ss_employee_id
        ):
            self.route_id = False


    @api.onchange("route_id")
    def _onchange_route_id(self):
        if self.route_id and self.route_id.ss_employee_id:
            self.so_employee_id = self.route_id.ss_employee_id.id


    # ── Secondary (van) sale: everything happens at confirmation ─────────────
    #
    # Business flow: the sales officer delivers (demand + damaged) to the store and
    # takes the damaged units back to the van scrap. So on confirm of a secondary
    # order we build exactly two stock documents, left for the officer to validate:
    #   1. one delivery  : a single line per product at demand + damaged, van -> store
    #                       (the sale line stays at demand, so only the demand is
    #                       invoiced);
    #   2. one receipt   : damaged, store -> van scrap.
    # A draft invoice for the demand is created; the customer pays for the demand only.

    def _action_confirm(self):
        result = super()._action_confirm()
        for order in self.filtered(lambda o: o.sale_type == "secondary"):
            order._ss_build_secondary_documents()
        for order in self.filtered(lambda o: o.sale_type == "primary"):
            order._ss_create_demand_invoice()
        return result

    def _ss_build_secondary_documents(self):
        self.ensure_one()
        damaged_lines = self.order_line.filtered(lambda line: line.damaged_qty > 0)
        delivery = self.picking_ids.filtered(
            lambda p: p.picking_type_id.code == "outgoing"
            and p.state not in ("done", "cancel")
        ).sorted("id")[:1]
        if delivery and damaged_lines:
            self._ss_add_damaged_to_delivery(delivery, damaged_lines)
            self._ss_create_damaged_receipt(delivery, damaged_lines)

    def _ss_employee_stock_location(self, scrap=False):
        """Return the SO employee's van stock (scrap=False) or van scrap (scrap=True)."""
        self.ensure_one()
        if not self.so_employee_id:
            return self.env["stock.location"]
        return self.env["stock.location"].search([
            ("ss_employee_id", "=", self.so_employee_id.id),
            ("scrap_location", "=", scrap),
        ], limit=1)

    def _ss_add_damaged_to_delivery(self, delivery, damaged_lines):
        """Grow each demand move to demand + damaged so the store receives the
        combined quantity on a single delivery line per product (e.g. 40 + 5 -> 45).

        The sale line stays at demand, so order-based invoicing still bills the demand
        only. Setting the absolute combined quantity keeps this idempotent across
        re-confirms. A zero-demand line (no move to grow) gets a standalone damaged
        move so the units are not dropped.
        """
        self.ensure_one()
        new_moves = self.env["stock.move"]
        changed = False
        for line in damaged_lines:
            move = delivery.move_ids.filtered(
                lambda m: m.sale_line_id == line and m.state not in ("done", "cancel")
            )[:1]
            if move:
                combined = line.product_uom_qty + line.damaged_qty
                if float_compare(
                    move.product_uom_qty, combined, precision_rounding=move.product_uom.rounding
                ) != 0:
                    move.product_uom_qty = combined
                    changed = True
            elif not delivery.move_ids.filtered(
                lambda m: not m.sale_line_id and m.product_id == line.product_id
            ):
                demand_move = delivery.move_ids.filtered(lambda m: m.sale_line_id)[:1]
                new_moves |= self.env["stock.move"].create({
                    "name": _("%s (Damaged)") % line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.damaged_qty,
                    "product_uom": line.product_uom.id,
                    "picking_id": delivery.id,
                    "location_id": (demand_move.location_id or delivery.location_id).id,
                    "location_dest_id": (demand_move.location_dest_id or delivery.location_dest_id).id,
                    "company_id": self.company_id.id,
                })
        if new_moves:
            new_moves._action_confirm(merge=False)
            changed = True
        if changed:
            delivery.action_assign()

    def _ss_create_damaged_receipt(self, delivery, damaged_lines):
        """Create one receipt that brings the damaged units back from the store into
        the van scrap location."""
        self.ensure_one()
        origin = _("%s - Damaged Return") % self.name
        if self.env["stock.picking"].search_count([
            ("origin", "=", origin),
            ("state", "!=", "cancel"),
        ]):
            # Idempotent: the damaged receipt already exists.
            return

        scrap_location = self._ss_employee_stock_location(scrap=True)
        if not scrap_location:
            _logger.warning(
                "No scrap location for employee %s; skipping damaged receipt for %s",
                self.so_employee_id.name, self.name,
            )
            return

        warehouse = delivery.picking_type_id.warehouse_id
        picking_type_in = warehouse.in_type_id if warehouse else self.env["stock.picking.type"].search([
            ("code", "=", "incoming"),
            ("company_id", "=", self.company_id.id),
        ], limit=1)
        if not picking_type_in:
            _logger.warning("No incoming operation type for the damaged receipt of %s", self.name)
            return

        store_location = delivery.location_dest_id
        self.env["stock.picking"].create({
            "picking_type_id": picking_type_in.id,
            "partner_id": self.partner_shipping_id.id or self.partner_id.id,
            "location_id": store_location.id,
            "location_dest_id": scrap_location.id,
            "origin": origin,
            "company_id": self.company_id.id,
            "move_ids": [
                (0, 0, {
                    "name": _("%s (Damaged Return)") % line.product_id.display_name,
                    "product_id": line.product_id.id,
                    "product_uom_qty": line.damaged_qty,
                    "product_uom": line.product_uom.id,
                    "location_id": store_location.id,
                    "location_dest_id": scrap_location.id,
                    "company_id": self.company_id.id,
                })
                for line in damaged_lines
            ],
        }).action_confirm()

    def _ss_create_demand_invoice(self):
        """Create a draft invoice for a sale order at confirmation.

        Temporarily overrides product invoice_policy to 'order' so that
        qty_to_invoice is computed from the ordered quantity, allowing
        invoicing at confirm regardless of the product-level setting.
        The invoice is left in draft — no auto-posting. Idempotent and
        never blocks confirmation.
        """
        self.ensure_one()
        if self.invoice_ids.filtered(lambda inv: inv.state != "cancel"):
            return

        # Temporarily force 'order' invoice policy so lines are invoiceable
        products = self.order_line.product_id
        original_policies = {p.id: p.invoice_policy for p in products}
        try:
            products.write({"invoice_policy": "order"})
            self.order_line._compute_qty_to_invoice()
            self.with_context(
                raise_if_nothing_to_invoice=False
            )._create_invoices(final=True)
        except Exception:
            _logger.exception(
                "Draft invoice creation failed for order %s",
                self.name or self.id,
            )
        finally:
            # Restore original invoice policies
            for product in products:
                if product.id in original_policies:
                    product.invoice_policy = original_policies[product.id]


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    damaged_qty = fields.Float(string="Damaged Quantity", default=0.0)

    @api.constrains("damaged_qty")
    def _check_damaged_qty(self):
        for line in self:
            if line.damaged_qty < 0:
                raise ValidationError(_("Damaged Quantity cannot be negative."))

    def _prepare_procurement_values(self, group_id=False):
        values = super()._prepare_procurement_values(group_id=group_id)
        if self.order_id.sale_type == "secondary" and self.order_id.so_employee_id:
            virtual_stock = self.order_id._ss_employee_stock_location(scrap=False)
            if virtual_stock:
                values["location_id"] = virtual_stock.id
        return values


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_custom_move_fields(self):
        fields_list = super()._get_custom_move_fields()
        fields_list += ["location_id"]
        return fields_list

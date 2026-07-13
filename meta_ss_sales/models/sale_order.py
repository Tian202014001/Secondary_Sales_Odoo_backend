# -*- coding: utf-8 -*-

import logging

from odoo import Command, _, api, fields, models
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

    damaged_picking_ids = fields.One2many(
        "stock.picking",
        compute="_compute_damaged_picking_ids",
        string="Damaged Receipts",
    )
    damaged_picking_count = fields.Integer(
        compute="_compute_damaged_picking_ids",
        string="Damaged Receipt Count",
    )

    @api.depends("picking_ids")
    def _compute_damaged_picking_ids(self):
        for order in self:
            damaged = self.env["stock.picking"].search([
                ("sale_id", "=", order.id),
                ("picking_type_id.code", "=", "incoming"),
            ])
            order.damaged_picking_ids = damaged
            order.damaged_picking_count = len(damaged)

    def action_view_damaged_receipt(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("stock.action_picking_tree_all")
        pickings = self.damaged_picking_ids
        if len(pickings) > 1:
            action["domain"] = [("id", "in", pickings.ids)]
        elif pickings:
            form_view = self.env.ref("stock.view_picking_form", raise_if_not_found=False)
            action["views"] = [(form_view.id if form_view else False, "form")]
            action["res_id"] = pickings.id
        else:
            action = {"type": "ir.actions.act_window_close"}
        return action

    @api.depends('picking_ids')
    def _compute_picking_ids(self):
        super()._compute_picking_ids()
        for order in self:
            if order.sale_type == 'secondary':
                deliveries = order.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
                order.delivery_count = len(deliveries)

    def action_view_delivery(self):
        if self.sale_type == 'secondary':
            deliveries = self.picking_ids.filtered(lambda p: p.picking_type_id.code == 'outgoing')
            return self._get_action_view_picking(deliveries)
        return super().action_view_delivery()

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
            "sale_id": self.id,
            "ss_picking_type": "secondary",
            "ss_transfer_category": "scrap",
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

        The invoice is left in draft and uses ordered demand quantity without
        changing product invoice policies, which are shared master data.
        """
        self.ensure_one()
        if self.invoice_ids.filtered(lambda inv: inv.state != "cancel"):
            return

        try:
            invoice_line_commands = self._ss_prepare_demand_invoice_line_commands()
            if not invoice_line_commands:
                return

            invoice_vals = self._prepare_invoice()
            invoice_vals["invoice_line_ids"] = invoice_line_commands
            self._create_account_invoices([invoice_vals], final=True)
        except Exception:
            _logger.exception(
                "Draft invoice creation failed for order %s",
                self.name or self.id,
            )

    def _ss_prepare_demand_invoice_line_commands(self):
        """Prepare invoice line commands for the sale order demand quantity."""
        self.ensure_one()
        commands = []
        pending_section = False
        sequence = 0
        has_product_line = False

        for line in self.order_line:
            if line.display_type == "line_section":
                pending_section = line
                continue
            if line.display_type == "line_note":
                commands.append(Command.create(line._prepare_invoice_line(sequence=sequence, quantity=0.0)))
                sequence += 1
                continue
            if line.product_uom_qty <= 0:
                continue
            if pending_section:
                commands.append(Command.create(pending_section._prepare_invoice_line(sequence=sequence, quantity=0.0)))
                sequence += 1
                pending_section = False
            commands.append(Command.create(line._prepare_invoice_line(
                sequence=sequence,
                quantity=line.product_uom_qty,
            )))
            sequence += 1
            has_product_line = True

        return commands if has_product_line else []


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

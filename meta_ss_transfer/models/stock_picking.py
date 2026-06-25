# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    ss_is_virtual_location_transfer = fields.Boolean(
        compute="_compute_ss_is_virtual_location_transfer"
    )
    ss_distributor_id = fields.Many2one(
        "res.partner",
        string="Distributor",
        domain="[('customer_type', '=', 'distributor')]",
        help="Distributor whose customer stock location is used as source.",
    )
    ss_destination_location_id = fields.Many2one(
        "stock.location",
        string="Destination Location",
        domain="[('usage', '!=', 'view')]",
        help="Virtual destination location for this transfer.",
    )

    ss_transfer_type = fields.Selection(
        [("load", "Van Load"), ("unload", "Van Unload")],
        string="Transfer Direction",
        default="load",
        required=True,
    )

    def _get_virtual_location_transfer_picking_type(self):
        """Return the custom operation type used for virtual location transfers."""
        return self.env.ref(
            "meta_ss_transfer.picking_type_virtual_location_transfer",
            raise_if_not_found=False,
        )

    def _get_van_unload_picking_type(self):
        """Return the custom operation type used for van unload transfers."""
        return self.env.ref(
            "meta_ss_transfer.picking_type_van_unload_transfer",
            raise_if_not_found=False,
        )

    def _is_virtual_location_transfer_operation(self):
        """Check whether this picking uses the virtual location transfer type."""
        self.ensure_one()
        transfer_type = self._get_virtual_location_transfer_picking_type()
        unload_type = self._get_van_unload_picking_type()
        return bool(
            (transfer_type and self.picking_type_id == transfer_type) or
            (unload_type and self.picking_type_id == unload_type)
        )

    @api.depends("picking_type_id")
    def _compute_ss_is_virtual_location_transfer(self):
        """Flag pickings that use the virtual location transfer operation type."""
        transfer_type = self._get_virtual_location_transfer_picking_type()
        unload_type = self._get_van_unload_picking_type()
        for picking in self:
            picking.ss_is_virtual_location_transfer = bool(
                (transfer_type and picking.picking_type_id == transfer_type) or
                (unload_type and picking.picking_type_id == unload_type)
            )

    @api.onchange("picking_type_id", "ss_distributor_id", "ss_transfer_type")
    def _onchange_ss_distributor_id(self):
        """Use the selected distributor customer location as transfer source or destination."""
        for picking in self:
            if (
                picking._is_virtual_location_transfer_operation()
                and picking.ss_distributor_id.property_stock_customer
            ):
                if picking.ss_transfer_type == "load":
                    picking.location_id = picking.ss_distributor_id.property_stock_customer
                else:
                    picking.location_dest_id = picking.ss_distributor_id.property_stock_customer

    @api.onchange("picking_type_id", "ss_destination_location_id", "ss_transfer_type")
    def _onchange_ss_destination_location_id(self):
        """Use the selected virtual destination as transfer destination or source."""
        for picking in self:
            if (
                picking._is_virtual_location_transfer_operation()
                and picking.ss_destination_location_id
            ):
                if picking.ss_transfer_type == "load":
                    picking.location_dest_id = picking.ss_destination_location_id
                else:
                    picking.location_id = picking.ss_destination_location_id

    @api.constrains(
        "picking_type_id",
        "ss_distributor_id",
        "ss_destination_location_id",
        "ss_transfer_type",
    )
    def _check_virtual_location_transfer_locations(self):
        """Require source distributor and destination for virtual transfers."""
        for picking in self.filtered(
            lambda p: p._is_virtual_location_transfer_operation()
        ):
            if not picking.ss_distributor_id:
                raise ValidationError(
                    _("Select a distributor for Virtual Location Transfers.")
                )
            if not picking.ss_distributor_id.property_stock_customer:
                raise ValidationError(
                    _("The selected distributor must have a customer stock location.")
                )
            if not picking.ss_destination_location_id:
                raise ValidationError(
                    _("Select a destination location for Virtual Location Transfers.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        """Set transfer source and destination when records are created based on direction."""
        transfer_type = self._get_virtual_location_transfer_picking_type()
        unload_type = self._get_van_unload_picking_type()
        transfer_id = transfer_type.id if transfer_type else False
        unload_id = unload_type.id if unload_type else False

        for vals in vals_list:
            picking_type_id = (
                vals.get("picking_type_id")
                or self.env.context.get("default_picking_type_id")
            )
            if picking_type_id not in (transfer_id, unload_id):
                continue

            direction = vals.get("ss_transfer_type", "load")
            distributor_id = vals.get("ss_distributor_id")
            distributor = False
            if distributor_id:
                distributor = self.env["res.partner"].browse(distributor_id)
            destination_id = vals.get("ss_destination_location_id")

            if direction == "load":
                if distributor and distributor.property_stock_customer and not vals.get("location_id"):
                    vals["location_id"] = distributor.property_stock_customer.id
                if destination_id and not vals.get("location_dest_id"):
                    vals["location_dest_id"] = destination_id
            else:  # unload
                if destination_id and not vals.get("location_id"):
                    vals["location_id"] = destination_id
                if distributor and distributor.property_stock_customer and not vals.get("location_dest_id"):
                    vals["location_dest_id"] = distributor.property_stock_customer.id

        return super().create(vals_list)

    def write(self, vals):
        """Keep stock locations synchronized after edits."""
        res = super().write(vals)
        if self.env.context.get("skip_ss_virtual_location_transfer_sync"):
            return res

        sync_fields = {
            "picking_type_id",
            "ss_distributor_id",
            "ss_destination_location_id",
            "ss_transfer_type",
        }
        if not sync_fields & set(vals):
            return res

        for picking in self.filtered(
            lambda p: p._is_virtual_location_transfer_operation()
            and p.state not in ("done", "cancel")
        ):
            sync_vals = {}
            if picking.ss_transfer_type == "load":
                if picking.ss_distributor_id.property_stock_customer:
                    sync_vals["location_id"] = (
                        picking.ss_distributor_id.property_stock_customer.id
                    )
                if picking.ss_destination_location_id:
                    sync_vals["location_dest_id"] = picking.ss_destination_location_id.id
            else:  # unload
                if picking.ss_destination_location_id:
                    sync_vals["location_id"] = picking.ss_destination_location_id.id
                if picking.ss_distributor_id.property_stock_customer:
                    sync_vals["location_dest_id"] = (
                        picking.ss_distributor_id.property_stock_customer.id
                    )
            if sync_vals:
                picking.with_context(
                    skip_ss_virtual_location_transfer_sync=True
                ).write(sync_vals)

        return res

    def button_validate(self):
        if self.env.context.get("skip_auto_scrap_transfer"):
            return super().button_validate()

        scrap_data = self._prepare_auto_scrap_data()
        res = super().button_validate()
        self._create_auto_scrap_transfers(scrap_data)
        return res

    def _prepare_auto_scrap_data(self):
        scrap_pickings_to_create = []
        for picking in self:
            if not picking._is_virtual_location_transfer_operation() or picking.ss_transfer_type != "unload":
                continue

            scrap_lines = []
            for move in picking.move_ids:
                if move.product_id.tracking == "none":
                    if move.ss_scrap_qty > 0:
                        scrap_lines.append({
                            "product": move.product_id,
                            "quantity": move.ss_scrap_qty,
                            "uom": move.product_uom,
                            "lots": []
                        })
                else:
                    lot_lines = []
                    for ml in move.move_line_ids:
                        if ml.ss_scrap_qty > 0:
                            lot_lines.append({
                                "lot": ml.lot_id,
                                "quantity": ml.ss_scrap_qty
                            })
                    if lot_lines:
                        scrap_lines.append({
                            "product": move.product_id,
                            "quantity": sum(l["quantity"] for l in lot_lines),
                            "uom": move.product_uom,
                            "lots": lot_lines
                        })
                    elif move.ss_scrap_qty > 0:
                        scrap_lines.append({
                            "product": move.product_id,
                            "quantity": move.ss_scrap_qty,
                            "uom": move.product_uom,
                            "lots": []
                        })

            if not scrap_lines:
                continue

            employee = picking.so_employee_id or picking.ss_destination_location_id.ss_employee_id
            distributor = picking.ss_distributor_id or picking.ss_destination_location_id.ss_distributor_id
            
            van_scrap_location = self.env["stock.location"].sudo().search([
                ("ss_location_type", "=", "van_loading"),
                ("scrap_location", "=", True),
                ("ss_employee_id", "=", employee.id),
                ("ss_distributor_id", "=", distributor.id),
                ("active", "=", True),
            ], limit=1)

            distributor_scrap_location = distributor.scrap_location_id

            if not van_scrap_location:
                raise ValidationError("Van Scrap Location not configured for employee/distributor.")
            if not distributor_scrap_location:
                raise ValidationError("Distributor Scrap Location not configured.")

            scrap_pickings_to_create.append({
                "origin_picking": picking,
                "van_scrap_location": van_scrap_location,
                "distributor_scrap_location": distributor_scrap_location,
                "distributor": distributor,
                "employee": employee,
                "lines": scrap_lines
            })
        return scrap_pickings_to_create

    def _create_auto_scrap_transfers(self, scrap_data):
        for item in scrap_data:
            origin_picking = item["origin_picking"]
            if origin_picking.state != "done":
                continue

            scrap_picking = self.env["stock.picking"].sudo().with_context(skip_ss_virtual_location_transfer_sync=True).create({
                "picking_type_id": origin_picking.picking_type_id.id,
                "location_id": item["van_scrap_location"].id,
                "location_dest_id": item["distributor_scrap_location"].id,
                "ss_distributor_id": item["distributor"].id,
                "ss_destination_location_id": origin_picking.ss_destination_location_id.id,
                "origin": f"Auto Scrap for {origin_picking.name}",
                "van_operation_type": "unload",
                "ss_transfer_type": "unload",
                "so_employee_id": item["employee"].id,
                "ss_picking_type": "secondary",
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": line["product"].display_name,
                            "product_id": line["product"].id,
                            "product_uom_qty": line["quantity"],
                            "product_uom": line["uom"].id,
                            "location_id": item["van_scrap_location"].id,
                            "location_dest_id": item["distributor_scrap_location"].id,
                        },
                    )
                    for line in item["lines"]
                ],
            })
            scrap_picking.action_confirm()

            for move in scrap_picking.move_ids:
                line_data = next((l for l in item["lines"] if l["product"].id == move.product_id.id), None)
                if not line_data:
                    continue
                move.move_line_ids.unlink()
                if line_data["lots"]:
                    for lot_info in line_data["lots"]:
                        self.env["stock.move.line"].sudo().create({
                            "picking_id": scrap_picking.id,
                            "move_id": move.id,
                            "product_id": move.product_id.id,
                            "lot_id": lot_info["lot"].id if lot_info["lot"] else False,
                            "quantity": lot_info["quantity"],
                            "location_id": item["van_scrap_location"].id,
                            "location_dest_id": item["distributor_scrap_location"].id,
                            "picked": True,
                        })
                else:
                    self.env["stock.move.line"].sudo().create({
                        "picking_id": scrap_picking.id,
                        "move_id": move.id,
                        "product_id": move.product_id.id,
                        "quantity": move.product_uom_qty,
                        "location_id": item["van_scrap_location"].id,
                        "location_dest_id": item["distributor_scrap_location"].id,
                        "picked": True,
                    })
                move.write({"picked": True})

            scrap_picking.with_context(skip_auto_scrap_transfer=True).button_validate()

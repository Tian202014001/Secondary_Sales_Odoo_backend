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

    def _is_virtual_location_transfer_operation(self):
        """Check whether this picking uses the virtual location transfer type."""
        self.ensure_one()
        transfer_type = self._get_virtual_location_transfer_picking_type()
        return bool(transfer_type and self.picking_type_id == transfer_type)

    @api.depends("picking_type_id")
    def _compute_ss_is_virtual_location_transfer(self):
        """Flag pickings that use the virtual location transfer operation type."""
        transfer_type = self._get_virtual_location_transfer_picking_type()
        for picking in self:
            picking.ss_is_virtual_location_transfer = bool(
                transfer_type and picking.picking_type_id == transfer_type
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
        if transfer_type:
            for vals in vals_list:
                picking_type_id = (
                    vals.get("picking_type_id")
                    or self.env.context.get("default_picking_type_id")
                )
                if picking_type_id != transfer_type.id:
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

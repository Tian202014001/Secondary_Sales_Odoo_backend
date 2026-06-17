# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SSRouteLine(models.Model):
    _name = "sale.route.line"
    _description = "Route Outlet Line"
    _order = "route_id, sequence, id"

    _sql_constraints = [
        ("route_outlet_unique", "unique(route_id, outlet_id)", "An outlet can only appear once in the same route."),
    ]

    route_id = fields.Many2one(
        "sale.route",
        string="Route",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(default=10)
    outlet_id = fields.Many2one(
        "res.partner",
        string="Outlet",
        required=True,
        domain="[('customer_type', '=', 'outlet')]",
    )
    
    active = fields.Boolean(default=True)

    @api.constrains("outlet_id")
    def _check_outlet_id(self):
        for line in self:
            if line.outlet_id and line.outlet_id.customer_type != "outlet":
                raise ValidationError(_("Route outlet must be an outlet contact."))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines.filtered("active")._sync_outlet_routes()
        return lines

    def write(self, vals):
        old_pairs = [(line.outlet_id, line.route_id) for line in self]
        result = super().write(vals)
        self._clear_unused_outlet_routes(old_pairs)
        self.filtered("active")._sync_outlet_routes()
        return result

    def unlink(self):
        old_pairs = [(line.outlet_id, line.route_id) for line in self]
        result = super().unlink()
        self._clear_unused_outlet_routes(old_pairs)
        return result

    def _sync_outlet_routes(self):
        for line in self:
            existing_route = line.outlet_id.outlet_route_id
            if existing_route and existing_route != line.route_id:
                raise ValidationError(
                    _("Outlet %(outlet)s is already assigned to route %(route)s.")
                    % {
                        "outlet": line.outlet_id.display_name,
                        "route": existing_route.display_name,
                    }
                )
            line.outlet_id.outlet_route_id = line.route_id

    def _clear_unused_outlet_routes(self, pairs):
        for outlet, route in pairs:
            if not outlet or not route or outlet.outlet_route_id != route:
                continue
            route_line_count = self.search_count([
                ("outlet_id", "=", outlet.id),
                ("route_id", "=", route.id),
                ("active", "=", True),
            ])
            if not route_line_count:
                outlet.outlet_route_id = False

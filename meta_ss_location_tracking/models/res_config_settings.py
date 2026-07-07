# -*- coding: utf-8 -*-

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    map_tile_url = fields.Char(
        string="Map Tile URL",
        config_parameter="meta_ss_location_tracking.map_tile_url",
        default="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        help="The OpenStreetMap tile layer URL format used to load map backgrounds in Leaflet.",
    )

    location_tracking_interval = fields.Integer(
        string="Location Tracking Interval (Seconds)",
        config_parameter="meta_ss_location_tracking.location_tracking_interval",
        default=5,
        help="The time interval in seconds at which the mobile client logs and syncs location coordinates.",
    )

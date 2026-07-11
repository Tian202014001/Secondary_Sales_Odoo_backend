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

    location_tracking_distance = fields.Integer(
        string="Location Tracking Distance (Meters)",
        config_parameter="meta_ss_location_tracking.location_tracking_distance",
        default=30,
        help="The distance interval in meters at which the mobile client logs and syncs location coordinates.",
    )

    location_tracking_type = fields.Selection(
        [
            ("time", "Time-Based"),
            ("distance", "Distance-Based"),
            ("both", "Both (Time or Distance)"),
        ],
        string="Location Tracking Type",
        config_parameter="meta_ss_location_tracking.location_tracking_type",
        default="time",
        help="Choose whether tracking logs are based on time interval, distance covered, or both.",
    )

    location_tracking_sync_interval = fields.Integer(
        string="Location Sync Interval (Seconds)",
        config_parameter="meta_ss_location_tracking.location_tracking_sync_interval",
        default=3600,
        help="How often (in seconds) the mobile client flushes its locally buffered GPS "
             "coordinates to the server. Sampling still happens at the tracking interval; "
             "this only controls the batch upload cadence. Default 3600 (1 hour).",
    )

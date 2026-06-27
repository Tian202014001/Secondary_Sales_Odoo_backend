from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    ss_attendance_radius = fields.Float(
        string="Attendance Radius (Meters)",
        default=50.0,
        help="Acceptable radius in meters for employees to check-in/out at this location."
    )

from odoo import models, fields

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    check_in_latitude = fields.Float(string="Check-in Latitude", digits=(10, 7))
    check_in_longitude = fields.Float(string="Check-in Longitude", digits=(10, 7))
    
    check_out_latitude = fields.Float(string="Check-out Latitude", digits=(10, 7))
    check_out_longitude = fields.Float(string="Check-out Longitude", digits=(10, 7))

    ss_distributor_id = fields.Many2one('res.partner', string="Distributor Checked In At")

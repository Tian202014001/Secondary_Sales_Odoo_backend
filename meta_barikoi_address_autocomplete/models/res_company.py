# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Bangladesh-specific address fields from Barikoi
    barikoi_division = fields.Char(
        string='Division',
        related='partner_id.barikoi_division',
        readonly=False,
        help='Bangladesh Division (Administrative Level 1)'
    )
    barikoi_district = fields.Char(
        string='District',
        related='partner_id.barikoi_district',
        readonly=False,
        help='Bangladesh District (Administrative Level 2)'
    )
    barikoi_upazila = fields.Char(
        string='Upazila',
        related='partner_id.barikoi_upazila',
        readonly=False,
        help='Bangladesh Upazila/Sub-District (Administrative Level 3)'
    )
    barikoi_union = fields.Char(
        string='Union',
        related='partner_id.barikoi_union',
        readonly=False,
        help='Bangladesh Union (Administrative Level 4)'
    )
    barikoi_place_id = fields.Char(
        string='Barikoi Place ID',
        related='partner_id.barikoi_place_id',
        readonly=False,
        help='Reference ID from Barikoi database'
    )
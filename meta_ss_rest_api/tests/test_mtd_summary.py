# -*- coding: utf-8 -*-
"""Aggregation tests for the MTD summary blocks.

Covers the risky new aggregation the MTD summary adds on top of the raw models:
the per-report *subtree* roll-up (a manager's line reflects everyone beneath
them, not just their own target lines), order counting by the correct ownership
field, and the visit productive-split derived from the ``sale.order.visit_id``
link. The range/scope resolvers are covered in ``test_dashboard_summary``.
"""

import calendar
from datetime import date

from odoo import fields
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.meta_ss_rest_api.utils.mtd_summary import (
    orders_block,
    reports_breakdown,
    visits_block,
)


@tagged("post_install", "-at_install")
class TestMtdSummaryBlocks(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Three-level chain so the subtree roll-up is non-trivial:
        # top -> mid -> leaf, with the target on the leaf.
        cls.top = cls.env["hr.employee"].create({"name": "MTD Top"})
        cls.mid = cls.env["hr.employee"].create(
            {"name": "MTD Mid", "parent_id": cls.top.id}
        )
        cls.leaf = cls.env["hr.employee"].create(
            {"name": "MTD Leaf", "parent_id": cls.mid.id}
        )
        cls.product = cls.env["product.product"].create({"name": "MTD SKU"})
        cls.outlet = cls.env["res.partner"].create(
            {"name": "MTD Outlet", "customer_type": "outlet"}
        )

        today = date.today()
        _, last_day = calendar.monthrange(today.year, today.month)
        cls.target = cls.env["sale.target"].create(
            {
                "month": "%02d" % today.month,
                "year": str(today.year),
                "date_from": date(today.year, today.month, 1),
                "date_to": date(today.year, today.month, last_day),
                "target_line_ids": [
                    (
                        0,
                        0,
                        {
                            "employee_id": cls.leaf.id,
                            "product_id": cls.product.id,
                            "target_qty": 50.0,
                        },
                    )
                ],
            }
        )

    def test_reports_breakdown_rolls_up_each_reports_subtree(self):
        # top's only direct report is mid; mid's figure must reflect the leaf's
        # target (rolled up through mid's own subtree), not mid's own lines (none).
        reports = reports_breakdown(self.env, self.mid, self.target.target_line_ids)
        self.assertEqual(len(reports), 1)
        row = reports[0]
        self.assertEqual(row["id"], self.mid.id)
        self.assertEqual(row["target_qty"], 50.0)
        self.assertEqual(row["achieved_qty"], 0.0)
        self.assertEqual(row["percent"], 0.0)
        # leaf sits under mid → one subordinate.
        self.assertEqual(row["sub_count"], 1)

    def test_orders_block_counts_secondary_by_so_employee(self):
        today = date.today()
        for _ in range(2):
            self.env["sale.order"].create(
                {
                    "partner_id": self.outlet.id,
                    "sale_type": "secondary",
                    "so_employee_id": self.leaf.id,
                }
            )
        block = orders_block(self.env, [self.leaf.id], "secondary", today, today)
        self.assertEqual(block["count"], 2)
        # A different employee's orders must not leak in.
        other = orders_block(self.env, [self.top.id], "secondary", today, today)
        self.assertEqual(other["count"], 0)

    def test_orders_block_counts_primary_via_sales_employee(self):
        # Regression: a primary order attributed via so_employee_id (the "Sales
        # Employee" field) must count even when user_id.employee_id differs.
        today = date.today()
        self.env["sale.order"].create(
            {
                "partner_id": self.outlet.id,
                "sale_type": "primary",
                "so_employee_id": self.leaf.id,
            }
        )
        block = orders_block(self.env, [self.leaf.id], "primary", today, today)
        self.assertEqual(block["count"], 1)
        self.assertGreaterEqual(block["value"], 0.0)

    def test_visits_block_splits_by_order_link(self):
        today = date.today()
        visit_with_order = self.env["outlet.visit"].create(
            {
                "employee_id": self.leaf.id,
                "outlet_id": self.outlet.id,
                "check_in_time": fields.Datetime.now(),
            }
        )
        self.env["outlet.visit"].create(
            {
                "employee_id": self.leaf.id,
                "outlet_id": self.outlet.id,
                "check_in_time": fields.Datetime.now(),
            }
        )
        # One order references the first visit → that visit is "with order".
        self.env["sale.order"].create(
            {
                "partner_id": self.outlet.id,
                "sale_type": "secondary",
                "so_employee_id": self.leaf.id,
                "visit_id": visit_with_order.id,
            }
        )
        block = visits_block(self.env, [self.leaf.id], today, today)
        self.assertEqual(block["total"], 2)
        self.assertEqual(block["with_order"], 1)
        self.assertEqual(block["no_order"], 1)

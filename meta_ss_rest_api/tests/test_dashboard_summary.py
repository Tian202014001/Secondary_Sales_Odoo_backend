# -*- coding: utf-8 -*-
"""Business-logic tests for the dashboard summary rollup.

Covers the risky new logic — role determination, team vs self target scoping,
and per-employee filtering — without the heavy delivered-stock setup. Achieved
quantity stays 0 here (no delivered orders); its computation is
``sale.target.line.achieved_target_qty``, exercised by the sale-target model
itself. This asserts the *aggregation and scoping* the dashboard adds on top.
"""

import calendar
from datetime import date

from odoo.exceptions import AccessDenied, ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.meta_ss_rest_api.utils.dashboard import (
    build_dashboard_summary,
    rollup,
)
from odoo.addons.meta_ss_rest_api.utils.mtd_summary import (
    resolve_dashboard_range,
    resolve_scoped_employee,
)


@tagged("post_install", "-at_install")
class TestDashboardSummary(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["hr.employee"].create({"name": "Dash Manager"})
        cls.rep = cls.env["hr.employee"].create(
            {"name": "Dash Rep", "parent_id": cls.manager.id}
        )
        cls.product = cls.env["product.product"].create({"name": "Dash SKU"})

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
                            "employee_id": cls.rep.id,
                            "product_id": cls.product.id,
                            "target_qty": 100.0,
                        },
                    )
                ],
            }
        )

    def test_rep_sees_own_target_and_no_team(self):
        data = build_dashboard_summary(self.env, self.rep)
        self.assertEqual(data["role"], "so")
        self.assertEqual(data["target"]["target_qty"], 100.0)
        self.assertEqual(data["target"]["achieved_qty"], 0.0)
        self.assertNotIn("team", data)
        self.assertFalse(data["is_checked_in"])

    def test_manager_target_is_team_rollup(self):
        data = build_dashboard_summary(self.env, self.manager)
        self.assertEqual(data["role"], "manager")
        # The manager's target card reflects the team (the rep's 100), not a
        # personal target the manager doesn't have.
        self.assertEqual(data["target"]["target_qty"], 100.0)
        self.assertEqual(data["team"]["total"], 1)
        self.assertEqual(data["team"]["present"], 0)
        member = data["team"]["members"][0]
        self.assertEqual(member["id"], self.rep.id)
        self.assertEqual(member["percent"], 0.0)
        self.assertFalse(member["is_checked_in"])

    def test_rollup_scopes_strictly_by_employee(self):
        lines = self.target.target_line_ids
        self.assertEqual(rollup(lines, [self.rep.id])["target_qty"], 100.0)
        # The manager has no target line of their own.
        self.assertEqual(rollup(lines, [self.manager.id])["target_qty"], 0.0)

    def test_resolve_dashboard_range_supports_presets_and_custom_dates(self):
        today = date.today()
        preset, date_from, date_to = resolve_dashboard_range({"preset": "today"})
        self.assertEqual(preset, "today")
        self.assertEqual(date_from, today)
        self.assertEqual(date_to, today)

        preset, date_from, date_to = resolve_dashboard_range({"preset": "month"})
        self.assertEqual(preset, "month")
        self.assertEqual(date_from.day, 1)
        self.assertEqual(date_to, today)

        preset, date_from, date_to = resolve_dashboard_range(
            {"date_from": "2026-07-01", "date_to": "2026-07-21"}
        )
        self.assertEqual(preset, "custom")
        self.assertEqual(str(date_from), "2026-07-01")
        self.assertEqual(str(date_to), "2026-07-21")

    def test_resolve_dashboard_range_rejects_invalid_inputs(self):
        with self.assertRaises(ValidationError):
            resolve_dashboard_range({"preset": "custom"})
        with self.assertRaises(ValidationError):
            resolve_dashboard_range({"date_from": "2026-07-21", "date_to": "2026-07-01"})

    def test_resolve_scoped_employee_stays_within_requester_subtree(self):
        scoped = resolve_scoped_employee(self.env, self.manager.id, self.rep.id)
        self.assertEqual(scoped.id, self.rep.id)

        root = resolve_scoped_employee(self.env, self.manager.id)
        self.assertEqual(root.id, self.manager.id)

        outsider = self.env["hr.employee"].create({"name": "Outside Rep"})
        with self.assertRaises(AccessDenied):
            resolve_scoped_employee(self.env, self.manager.id, outsider.id)

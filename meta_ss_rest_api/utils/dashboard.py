# -*- coding: utf-8 -*-
"""Landing-dashboard summary assembly.

Pure helpers that build the role-aware payload for ``/dashboard/summary``:
an attendance snapshot, a target-achievement rollup (Σ delivered ÷ Σ target
over the active monthly ``sale.target`` lines), and — for managers — a team
roll-up with per-subordinate achievement.

Kept out of the controller so the rollup math is unit-testable in isolation
(see ``tests/test_dashboard_summary.py``).
"""

from odoo import fields


def attendance_snapshot(env, employee):
    """Current open shift for ``employee`` (mirrors /hr/attendance/status)."""
    active = env["hr.attendance"].sudo().search(
        [("employee_id", "=", employee.id), ("check_out", "=", False)],
        order="check_in desc",
        limit=1,
    )
    return {
        "is_checked_in": bool(active),
        "check_in_time": active.check_in.strftime("%Y-%m-%d %H:%M:%S")
        if active
        else None,
    }


def active_target_lines(env, on_date):
    """All ``sale.target.line`` whose parent target period covers ``on_date``."""
    targets = env["sale.target"].sudo().search(
        [("date_from", "<=", on_date), ("date_to", ">=", on_date)]
    )
    return targets.mapped("target_line_ids")


def rollup(lines, employee_ids):
    """Σ delivered ÷ Σ target for ``employee_ids`` over ``lines``.

    ``achieved_target_qty`` is ``sale.target.line``'s own delivered-quantity
    compute, so the dashboard figure always matches the Sale Target record
    exactly rather than re-deriving it.
    """
    emp_set = set(employee_ids)
    selected = lines.filtered(lambda line: line.employee_id.id in emp_set)
    return {
        "achieved_qty": float(sum(selected.mapped("achieved_target_qty"))),
        "target_qty": float(sum(selected.mapped("target_qty"))),
    }


def _percent(rolled):
    target = rolled["target_qty"]
    return round(rolled["achieved_qty"] / target * 100.0, 1) if target > 0 else 0.0


def team_snapshot(env, subordinates, on_date, target_lines):
    """Present/total plus per-subordinate attendance and achievement %."""
    date_start = "%s 00:00:00" % on_date
    date_end = "%s 23:59:59" % on_date

    # One query for the day's attendances across all subordinates; keep the
    # earliest check-in per employee.
    att_by_emp = {}
    if subordinates:
        for att in env["hr.attendance"].sudo().search(
            [
                ("employee_id", "in", subordinates.ids),
                ("check_in", ">=", date_start),
                ("check_in", "<=", date_end),
            ],
            order="employee_id, check_in",
        ):
            att_by_emp.setdefault(att.employee_id.id, att)

    members = []
    present = 0
    for sub in subordinates:
        att = att_by_emp.get(sub.id)
        checked_in = bool(att and not att.check_out)
        if checked_in:
            present += 1
        members.append(
            {
                "id": sub.id,
                "name": sub.name,
                "percent": _percent(rollup(target_lines, [sub.id])),
                "is_checked_in": checked_in,
            }
        )

    return {
        "present": present,
        "total": len(subordinates),
        "members": members,
    }


def build_dashboard_summary(env, employee):
    """Assemble the full role-aware summary for ``employee``.

    A manager (anyone with active ``child_of`` subordinates) gets a *team*
    target rollup and roster; everyone else gets their own rollup. Team figures
    are strictly scoped to the caller's own subordinate hierarchy.
    """
    on_date = fields.Date.today().strftime("%Y-%m-%d")

    subordinates = env["hr.employee"].sudo().search(
        [
            ("id", "child_of", employee.id),
            ("id", "!=", employee.id),
            ("active", "=", True),
        ],
        order="name asc",
    )
    is_manager = bool(subordinates)

    target_lines = active_target_lines(env, on_date)
    target_employee_ids = subordinates.ids if is_manager else [employee.id]

    data = {
        "role": "manager" if is_manager else "so",
        "target": rollup(target_lines, target_employee_ids),
    }
    data.update(attendance_snapshot(env, employee))

    if is_manager:
        data["team"] = team_snapshot(env, subordinates, on_date, target_lines)

    return data

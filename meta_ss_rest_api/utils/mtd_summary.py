# -*- coding: utf-8 -*-
"""Month-to-Date (date-range) summary assembly for the landing dashboard.

Pure, unit-testable helpers that build the role-aware payload for
``/dashboard/summary/mtd``. Everything is scoped to the requesting employee and
their ``child_of`` subtree — a manager never sees outside their own hierarchy.

The payload has four blocks, each honouring the selected ``[date_from, date_to]``
range except *achievement*, which is tied to the monthly Sale Target period
(``sale.target.line`` already computes ``achieved_target_qty`` over that period):

* **attendance** — my (+ team) present / absent *day counts*. Absent = working
  days (from the employee's ``resource.calendar``, capped at today) minus present
  days minus approved-leave days.
* **achievement** — Σ delivered qty ÷ Σ target qty (SKU quantity), rolled up over
  the caller's subtree, plus a per-direct-report breakdown where each report's
  figure is *their own* subtree roll-up (so the hierarchy recurses).
* **orders** — primary & secondary, count + total value; ``my`` when the role
  creates that type, ``team`` as the subtree roll-up.
* **visits** — total / with-order / no-order (a visit is "with order" when a
  ``sale.order`` references it via ``visit_id``).

Which sub-blocks are present is decided per-metric from two live signals only —
whether the caller has subordinates, and whether their mobile group grants the
matching ``*_ORDERS_CREATE`` UI resource — so no role names are hard-coded.
"""

from datetime import datetime, time, timedelta

from odoo import fields
from odoo.exceptions import AccessDenied, ValidationError
from odoo.osv import expression

from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey
from odoo.addons.meta_ss_rest_api.utils.mobile_policy import MobilePolicy
from odoo.addons.meta_ss_rest_api.utils.dashboard import active_target_lines, attendance_snapshot

# Orders counted toward "total orders / total value" — everything except cancelled.
NON_CANCELLED = ("draft", "sent", "sale", "done")


# ---------------------------------------------------------------------------
# small shared helpers
# ---------------------------------------------------------------------------

def _bounds(date_from, date_to):
    """Datetime string bounds spanning the whole day range (naive, UTC-ish)."""
    return "%s 00:00:00" % date_from, "%s 23:59:59" % date_to


def _percent(achieved, target):
    return round(achieved / target * 100.0, 1) if target > 0 else 0.0


def _parse_date(value, label):
    try:
        return fields.Date.from_string(str(value))
    except Exception as exc:
        raise ValidationError("'%s' must be a valid YYYY-MM-DD date." % label) from exc


def resolve_dashboard_range(payload):
    """Return the selected dashboard preset and inclusive date range."""
    payload = payload or {}
    preset = (payload.get("preset") or payload.get("range") or "today").strip().lower()
    date_from_raw = payload.get("date_from") or payload.get("start_date")
    date_to_raw = payload.get("date_to") or payload.get("end_date")
    today = fields.Date.today()

    if date_from_raw or date_to_raw:
        if not date_from_raw or not date_to_raw:
            raise ValidationError("Both 'date_from' and 'date_to' are required for a custom range.")
        date_from = _parse_date(date_from_raw, "date_from")
        date_to = _parse_date(date_to_raw, "date_to")
        preset = "custom"
    else:
        if preset in ("mtd", "month_to_date"):
            preset = "month"
        if preset == "today":
            date_from = date_to = today
        elif preset == "week":
            date_from = today - timedelta(days=today.weekday())
            date_to = today
        elif preset == "month":
            date_from = today.replace(day=1)
            date_to = today
        elif preset == "custom":
            raise ValidationError("Custom range requires both 'date_from' and 'date_to'.")
        else:
            raise ValidationError("Invalid preset. Use today, week, month, or custom.")

    if date_from > date_to:
        raise ValidationError("'date_from' cannot be after 'date_to'.")
    return preset, date_from, date_to


def resolve_scoped_employee(env, root_employee_id, scoped_employee_id=None):
    """Resolve an optional subordinate dashboard scope within the caller's subtree."""
    root = env["hr.employee"].sudo().browse(int(root_employee_id)).exists()
    if not root:
        raise ValidationError("The requesting employee could not be found.")
    if not scoped_employee_id:
        return root

    try:
        scoped_employee_id = int(scoped_employee_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'scope_employee_id' must be a valid integer id.") from exc

    allowed_scope = env["hr.employee"].sudo().search([
        ("id", "child_of", root.id),
        ("active", "=", True),
    ])
    scoped = allowed_scope.filtered(lambda employee: employee.id == scoped_employee_id)[:1]
    if not scoped:
        raise AccessDenied("You do not have access to this dashboard scope.")
    return scoped


def _current_checked_in_employee_ids(env, employees):
    if not employees:
        return set()
    attendances = env["hr.attendance"].sudo().search([
        ("employee_id", "in", employees.ids),
        ("check_out", "=", False),
    ])
    return set(attendances.mapped("employee_id").ids)


# ---------------------------------------------------------------------------
# attendance
# ---------------------------------------------------------------------------

def _present_days_by_employee(env, employee_ids, date_from, date_to):
    """{employee_id: number of distinct calendar dates checked in} over the range."""
    dt_from, dt_to = _bounds(date_from, date_to)
    atts = env["hr.attendance"].sudo().search([
        ("employee_id", "in", list(employee_ids)),
        ("check_in", ">=", dt_from),
        ("check_in", "<=", dt_to),
    ])
    seen = {}
    for att in atts:
        if not att.check_in:
            continue
        seen.setdefault(att.employee_id.id, set()).add(att.check_in.date())
    return {emp_id: len(dates) for emp_id, dates in seen.items()}


def _approved_leave_days_by_employee(env, employee_ids, date_from, date_to):
    """{employee_id: approved-leave days} that overlap the range."""
    dt_from, dt_to = _bounds(date_from, date_to)
    leaves = env["hr.leave"].sudo().search([
        ("employee_id", "in", list(employee_ids)),
        ("state", "=", "validate"),
        ("date_from", "<=", dt_to),
        ("date_to", ">=", dt_from),
    ])
    out = {}
    for lv in leaves:
        out[lv.employee_id.id] = out.get(lv.employee_id.id, 0.0) + (lv.number_of_days or 0.0)
    return out


def _working_days(employee, date_from, date_to):
    """Scheduled working days for ``employee`` in the (already today-capped) range.

    Uses the employee's resource calendar; falls back to counting every day when
    no calendar is configured. ``compute_leaves=False`` — global calendar leaves
    are irrelevant here; we subtract *approved* time-off separately.
    """
    calendar = employee.resource_calendar_id or employee.company_id.resource_calendar_id
    span_days = (date_to - date_from).days + 1
    if not calendar:
        return span_days
    dt_from = datetime.combine(date_from, time.min)
    dt_to = datetime.combine(date_to, time.max)
    try:
        return int(round(calendar.get_work_days_count(dt_from, dt_to, compute_leaves=False)))
    except Exception:
        return span_days


def attendance_block(env, employees, date_from, date_to):
    """Aggregate present / absent *person-days* across ``employees`` for the range."""
    if not employees:
        return {"present": 0, "absent": 0}
    today = fields.Date.today()
    capped_to = min(date_to, today)
    ids = employees.ids
    present_by = _present_days_by_employee(env, ids, date_from, capped_to)
    leave_by = _approved_leave_days_by_employee(env, ids, date_from, capped_to)

    present = absent = 0
    for emp in employees:
        p = present_by.get(emp.id, 0)
        present += p
        if capped_to >= date_from:
            worked = _working_days(emp, date_from, capped_to)
            leave = int(round(leave_by.get(emp.id, 0.0)))
            absent += max(0, worked - p - leave)
    return {"present": present, "absent": absent}


# ---------------------------------------------------------------------------
# orders
# ---------------------------------------------------------------------------

def orders_block(env, employee_ids, sale_type, date_from, date_to, currency=None, company=None):
    """Count + total value of non-cancelled ``sale_type`` orders over the range.

    An order counts for an employee when *either* ownership field matches — the
    custom ``so_employee_id`` ("Sales Employee", set on both primary and
    secondary orders) or the standard ``user_id.employee_id`` (the salesperson).
    This mirrors the list endpoint's ``build_sale_order_domain`` so the dashboard
    figure always matches the list a tap-through opens. ``state in NON_CANCELLED``
    keeps confirmed orders (``sale``/``done``) as well as open quotations.

    When ``currency`` is given, each order's ``amount_total`` is converted from
    its own currency into it (so a mixed-currency sum is valid); otherwise the
    raw per-order totals are summed.
    """
    dt_from, dt_to = _bounds(date_from, date_to)
    ids = list(employee_ids)
    owner = expression.OR(
        [
            [("so_employee_id", "in", ids)],
            [("user_id.employee_id", "in", ids)],
        ]
    )
    domain = expression.AND(
        [
            owner,
            [
                ("sale_type", "=", sale_type),
                ("date_order", ">=", dt_from),
                ("date_order", "<=", dt_to),
                ("state", "in", list(NON_CANCELLED)),
            ],
        ]
    )
    orders = env["sale.order"].sudo().search(domain)

    if currency is None:
        value = float(sum(orders.mapped("amount_total")))
    else:
        total = 0.0
        for order in orders:
            order_currency = order.currency_id or currency
            amount = order.amount_total
            if order_currency and order_currency != currency:
                convert_date = (
                    order.date_order.date() if order.date_order else fields.Date.today()
                )
                try:
                    amount = order_currency._convert(
                        amount,
                        currency,
                        company or order.company_id or env.company,
                        convert_date,
                    )
                except Exception:
                    # Missing/one-off rate must not fail the whole summary; fall
                    # back to the raw amount rather than raising.
                    pass
            total += amount
        value = float(total)

    return {"count": len(orders), "value": value}


# ---------------------------------------------------------------------------
# visits
# ---------------------------------------------------------------------------

def visits_block(env, employee_ids, date_from, date_to):
    """Total visits + productive split (a visit is 'with order' when referenced
    by a non-cancelled ``sale.order.visit_id``)."""
    dt_from, dt_to = _bounds(date_from, date_to)
    visits = env["outlet.visit"].sudo().search([
        ("employee_id", "in", list(employee_ids)),
        ("check_in_time", ">=", dt_from),
        ("check_in_time", "<=", dt_to),
    ])
    total = len(visits)
    if not total:
        return {"total": 0, "with_order": 0, "no_order": 0}
    ordered_ids = set(env["sale.order"].sudo().search([
        ("visit_id", "in", visits.ids),
        ("state", "in", list(NON_CANCELLED)),
    ]).mapped("visit_id").ids)
    with_order = sum(1 for v in visits if v.id in ordered_ids)
    return {"total": total, "with_order": with_order, "no_order": total - with_order}


# ---------------------------------------------------------------------------
# achievement (SKU quantity, monthly target period)
# ---------------------------------------------------------------------------

def _achievement_over(target_lines, employee_ids):
    emp_set = set(employee_ids)
    selected = target_lines.filtered(lambda line: line.employee_id.id in emp_set)
    achieved = float(sum(selected.mapped("achieved_target_qty")))
    target = float(sum(selected.mapped("target_qty")))
    return {
        "achieved_qty": achieved,
        "target_qty": target,
        "percent": _percent(achieved, target),
    }


def reports_breakdown(env, direct_reports, target_lines):
    """Per direct-report achievement, each rolled up over *that report's* subtree."""
    checked_in_ids = _current_checked_in_employee_ids(env, direct_reports)
    out = []
    for rep in direct_reports:
        sub = env["hr.employee"].sudo().search([
            ("id", "child_of", rep.id),
            ("active", "=", True),
        ])
        block = _achievement_over(target_lines, sub.ids)
        block.update({
            "id": rep.id,
            "name": rep.name,
            "sub_count": max(0, len(sub) - 1),
            "is_checked_in": rep.id in checked_in_ids,
        })
        out.append(block)
    return out


# ---------------------------------------------------------------------------
# assembly
# ---------------------------------------------------------------------------

def build_mtd_summary(env, employee, mobile_user, date_from, date_to, preset="custom"):
    """Assemble the full role-aware MTD summary for ``employee`` over the range."""
    policy = MobilePolicy(mobile_user)
    can_primary = policy.has_ui_access(AccessKey.PRIMARY_ORDERS_CREATE)
    can_secondary = policy.has_ui_access(AccessKey.SECONDARY_ORDERS_CREATE)

    direct_reports = env["hr.employee"].sudo().search(
        [("parent_id", "=", employee.id), ("active", "=", True)], order="name asc"
    )
    scope = env["hr.employee"].sudo().search(
        [("id", "child_of", employee.id), ("active", "=", True)]
    )
    subtree = scope.filtered(lambda e: e.id != employee.id)
    has_team = bool(subtree)
    my_ids = [employee.id]

    # Reporting currency = the employee's company currency. Order amounts are
    # converted into it so the client can format with the right symbol and a
    # mixed-currency sum stays valid.
    company = employee.company_id or env.company
    currency = company.currency_id

    data = {
        "date_from": str(date_from),
        "date_to": str(date_to),
        "preset": preset,
        "role": "manager" if has_team else "so",
        "has_team": has_team,
        "scope_employee_id": employee.id,
        "scope_employee_name": employee.name,
        "is_scoped": bool(mobile_user.employee_id and employee.id != mobile_user.employee_id.id),
        "currency": {
            "symbol": currency.symbol or currency.name or "",
            "code": currency.name or "",
            "position": currency.position or "after",
        },
    }
    data.update(attendance_snapshot(env, employee))

    # ---- attendance (per-person; always a "my", team when there are subs) ----
    attendance = {"my": attendance_block(env, employee, date_from, date_to)}
    if has_team:
        attendance["team"] = attendance_block(env, subtree, date_from, date_to)
    data["attendance"] = attendance

    # ---- achievement (monthly target period) ----
    on_date = fields.Date.today().strftime("%Y-%m-%d")
    target_lines = active_target_lines(env, on_date)
    achievement = {}
    my_ach = _achievement_over(target_lines, scope.ids)  # self + whole subtree
    data["target"] = {
        "achieved_qty": my_ach["achieved_qty"],
        "target_qty": my_ach["target_qty"],
    }
    if my_ach["target_qty"] > 0 or not has_team:
        achievement["my"] = my_ach
    if has_team:
        reports = reports_breakdown(env, direct_reports, target_lines)
        achievement["reports"] = reports
        data["team"] = {
            "present": sum(1 for report in reports if report.get("is_checked_in")),
            "total": len(reports),
            "members": [
                {
                    "id": report["id"],
                    "name": report["name"],
                    "percent": report["percent"],
                    "is_checked_in": report["is_checked_in"],
                    "sub_count": report["sub_count"],
                    "achieved_qty": report["achieved_qty"],
                    "target_qty": report["target_qty"],
                }
                for report in reports
            ],
        }
    data["achievement"] = achievement

    # ---- orders (primary / secondary · my / team) ----
    orders = {"primary": {}, "secondary": {}}
    for sale_type, can_create in (("primary", can_primary), ("secondary", can_secondary)):
        if can_create:
            orders[sale_type]["my"] = orders_block(
                env, my_ids, sale_type, date_from, date_to, currency=currency, company=company
            )
        if has_team:
            team = orders_block(
                env, subtree.ids, sale_type, date_from, date_to, currency=currency, company=company
            )
            if team["count"] > 0:
                orders[sale_type]["team"] = team
    data["orders"] = orders

    # ---- visits (my when the role does field visits; team when there are subs) ----
    visits = {}
    if can_secondary:
        visits["my"] = visits_block(env, my_ids, date_from, date_to)
    if has_team:
        visits["team"] = visits_block(env, subtree.ids, date_from, date_to)
    data["visits"] = visits

    return data

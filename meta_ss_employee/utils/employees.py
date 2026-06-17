# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.osv import expression

from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination


def build_employee_domain(env, payload):
    domain = [("active", "=", True)]

    distributor_id = payload.get("distributor_id")
    if distributor_id:
        try:
            distributor_id = int(distributor_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'distributor_id' must be a valid integer id.") from exc
        distributor = env["res.partner"].sudo().browse(distributor_id).exists()
        if not distributor or distributor.customer_type != "distributor":
            raise ValidationError("Distributor not found.")
        domain.append(("distributor_contact_ids", "in", [distributor.id]))

    manager_id = payload.get("manager_id") or payload.get("parent_id")
    if manager_id:
        try:
            manager_id = int(manager_id)
        except (TypeError, ValueError) as exc:
            raise ValidationError("'manager_id' must be a valid integer id.") from exc
        domain.append(("parent_id", "=", manager_id))

    search = (payload.get("search") or "").strip()
    if search:
        domain = expression.AND([
            domain,
            expression.OR([
                [("name", "ilike", search)],
                [("work_phone", "ilike", search)],
                [("mobile_phone", "ilike", search)],
                [("work_email", "ilike", search)],
            ]),
        ])

    return domain


def serialize_employee(employee):
    return {
        "id": employee.id,
        "name": employee.name,
        "work_phone": employee.work_phone or None,
        "mobile_phone": employee.mobile_phone or None,
        "work_email": employee.work_email or None,
        "job_title": employee.job_title or None,
        "distributors": [
            {
                "id": dist.id,
                "name": dist.name,
            }
            for dist in employee.distributor_contact_ids
        ],
        "assigned_routes": [
            {
                "id": route.id,
                "name": route.name,
                "code": route.code or None,
            }
            for route in employee.assigned_route_ids
        ],
    }


def get_employee_pagination(payload):
    return get_pagination(payload)


def prepare_employee_values(env, payload):
    name = (payload.get("name") or "").strip()
    if not name:
        raise ValidationError("Name is required.")

    distributor_ids = payload.get("distributor_ids") or payload.get("distributor_contact_ids")
    if not distributor_ids:
        dist_id = payload.get("distributor_id") or payload.get("distributor_contact_id")
        if dist_id:
            distributor_ids = [dist_id]
        else:
            raise ValidationError("Distributor ID(s) required.")

    if not isinstance(distributor_ids, list):
        raise ValidationError("Distributor IDs must be a list.")

    try:
        distributor_ids = [int(did) for did in distributor_ids]
    except (TypeError, ValueError) as exc:
        raise ValidationError("Distributor IDs must be integers.") from exc

    distributors = env["res.partner"].sudo().search([("id", "in", distributor_ids)])
    if len(distributors) != len(distributor_ids):
        raise ValidationError("One or more distributors not found.")
    for dist in distributors:
        if dist.customer_type != "distributor":
            raise ValidationError("One or more selected partners are not distributors.")

    vals = {
        "name": name,
        "distributor_contact_ids": [(6, 0, distributor_ids)],
        "work_email": (payload.get("work_email") or payload.get("email") or "").strip() or False,
        "mobile_phone": (payload.get("mobile_phone") or payload.get("phone") or "").strip() or False,
        "work_phone": (payload.get("work_phone") or "").strip() or False,
        "job_title": (payload.get("job_title") or "Sales Officer").strip(),
    }

    # Handle assigned route ids
    route_ids = payload.get("assigned_route_ids")
    if route_ids is not None:
        if not isinstance(route_ids, list):
            raise ValidationError("assigned_route_ids must be a list of integers.")
        try:
            route_ids = [int(rid) for rid in route_ids]
        except (TypeError, ValueError) as exc:
            raise ValidationError("assigned_route_ids must contain valid integers.") from exc

        # Verify routes exist
        existing_routes = env["sale.route"].sudo().search([("id", "in", route_ids)])
        if len(existing_routes) != len(route_ids):
            raise ValidationError("One or more assigned route IDs are invalid.")

        vals["assigned_route_ids"] = [(6, 0, route_ids)]

    return vals


def prepare_employee_update_values(env, payload, employee):
    vals = {}

    if "name" in payload:
        name = (payload.get("name") or "").strip()
        if not name:
            raise ValidationError("Name cannot be empty.")
        vals["name"] = name

    distributor_ids = payload.get("distributor_ids") or payload.get("distributor_contact_ids")
    if distributor_ids is None:
        # Check single id fallback
        dist_id = payload.get("distributor_id") or payload.get("distributor_contact_id")
        if dist_id is not None:
            distributor_ids = [dist_id]

    if distributor_ids is not None:
        if not isinstance(distributor_ids, list):
            raise ValidationError("Distributor IDs must be a list.")
        try:
            distributor_ids = [int(did) for did in distributor_ids]
        except (TypeError, ValueError) as exc:
            raise ValidationError("Distributor IDs must be integers.") from exc

        distributors = env["res.partner"].sudo().search([("id", "in", distributor_ids)])
        if len(distributors) != len(distributor_ids):
            raise ValidationError("One or more distributors not found.")
        for dist in distributors:
            if dist.customer_type != "distributor":
                raise ValidationError("One or more selected partners are not distributors.")
        vals["distributor_contact_ids"] = [(6, 0, distributor_ids)]

    if "work_email" in payload or "email" in payload:
        vals["work_email"] = (payload.get("work_email") or payload.get("email") or "").strip() or False

    if "mobile_phone" in payload or "phone" in payload:
        vals["mobile_phone"] = (payload.get("mobile_phone") or payload.get("phone") or "").strip() or False

    if "work_phone" in payload:
        vals["work_phone"] = (payload.get("work_phone") or "").strip() or False

    if "job_title" in payload:
        vals["job_title"] = (payload.get("job_title") or "Sales Officer").strip()

    route_ids = payload.get("assigned_route_ids")
    if route_ids is not None:
        if not isinstance(route_ids, list):
            raise ValidationError("assigned_route_ids must be a list of integers.")
        try:
            route_ids = [int(rid) for rid in route_ids]
        except (TypeError, ValueError) as exc:
            raise ValidationError("assigned_route_ids must contain valid integers.") from exc

        existing_routes = env["sale.route"].sudo().search([("id", "in", route_ids)])
        if len(existing_routes) != len(route_ids):
            raise ValidationError("One or more assigned route IDs are invalid.")

        vals["assigned_route_ids"] = [(6, 0, route_ids)]

    return vals

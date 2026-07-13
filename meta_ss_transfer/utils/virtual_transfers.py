# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero

from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination
from odoo.addons.meta_ss_rest_api.utils.helpers import _create_move_line, _get_float, _get_positive_float, _get_non_negative_float, _get_integer_id, _get_employee, _get_lot


def get_virtual_transfer_picking_type(env, van_operation_type=None):
    if van_operation_type == "unload":
        picking_type = env.ref(
            "meta_ss_transfer.picking_type_van_unload_transfer",
            raise_if_not_found=False,
        )
        if not picking_type:
            raise ValidationError("Van Unload Transfer operation type is not configured.")
        return picking_type
    picking_type = env.ref(
        "meta_ss_transfer.picking_type_virtual_location_transfer",
        raise_if_not_found=False,
    )
    if not picking_type:
        raise ValidationError("Virtual Location Transfer operation type is not configured.")
    return picking_type


def get_employee_transfer_context(env, payload):
    employee = _get_employee(env, payload.get("employee_id"))
    destination = _get_destination_location_from_payload(env, payload)
    if destination:
        employee = destination.ss_employee_id.sudo()
        distributor = destination.ss_distributor_id.sudo()
    else:
        dist_id = payload.get("distributor_id")
        if dist_id:
            distributor = env["res.partner"].sudo().browse(int(dist_id)).exists()
        else:
            distributors = employee.distributor_contact_ids.sudo()
            if len(distributors) == 1:
                distributor = distributors[0]
            elif len(distributors) > 1:
                raise ValidationError("Employee is assigned to multiple distributors. Please provide a destination_location_id or distributor_id.")
            else:
                distributor = env["res.partner"].sudo()
    if not distributor:
        raise ValidationError("Select a Van Loading Location before loading transfer stock.")
    if distributor.customer_type != "distributor":
        raise ValidationError("The employee's assigned contact is not a distributor.")
    
    van_op_type = payload.get("van_operation_type") or "load"
    if van_op_type == "unload" and destination:
        source_location = destination
    else:
        source_location = distributor.property_stock_customer

    if not source_location:
        raise ValidationError("The source stock location is not configured.")
    return employee, distributor, source_location


def serialize_virtual_transfer_prepare(env, payload):
    employee = _get_employee(env, payload.get("employee_id"))
    dist_id = payload.get("distributor_id")
    if dist_id:
        distributor = env["res.partner"].sudo().browse(int(dist_id)).exists()
    else:
        distributors = employee.distributor_contact_ids.sudo()
        distributor = distributors[0] if distributors else env["res.partner"].sudo()
    source_location = distributor.property_stock_customer if distributor else False
    destinations = _get_prepare_van_locations(env, employee, distributor)
    return {
        "employee": _serialize_employee(employee),
        "distributor": _serialize_distributor(distributor),
        "source_location": _serialize_location(source_location),
        "destination_locations": [
            serialize_van_loading_location(location) for location in destinations
        ],
    }


def build_virtual_transfer_product_domain(env, payload):
    _employee, _distributor, source_location = get_employee_transfer_context(env, payload)
    product_ids = _get_available_product_ids(env, source_location)
    domain = [
        ("id", "in", product_ids),
        ("active", "=", True),
        ("type", "!=", "service"),
    ]

    search = (payload.get("search") or payload.get("name") or "").strip()
    if search:
        domain = expression.AND([
            domain,
            expression.OR([
                [("name", "ilike", search)],
                [("default_code", "ilike", search)],
                [("barcode", "ilike", search)],
            ]),
        ])
    return source_location, domain


def serialize_transfer_products(env, products, source_location, payload=None):
    payload = payload or {}
    van_op_type = payload.get("van_operation_type") or "load"
    
    van_scrap_location = env["stock.location"]
    if van_op_type == "unload" and source_location.ss_location_type == "van_loading":
        employee = _get_employee(env, payload.get("employee_id"))
        destination = _get_destination_location_from_payload(env, payload)
        if destination:
            employee = destination.ss_employee_id.sudo()
            distributor = destination.ss_distributor_id.sudo()
        else:
            distributor = env["res.partner"].sudo()
            
        van_scrap_location = env["stock.location"].sudo().search([
            ("ss_location_type", "=", "van_loading"),
            ("scrap_location", "=", True),
            ("ss_employee_id", "=", employee.id),
            ("ss_distributor_id", "=", distributor.id),
            ("active", "=", True),
        ], limit=1)

    result = []
    for product in products:
        item = {
            "id": product.id,
            "name": product.display_name,
            "default_code": product.default_code or None,
            "barcode": product.barcode or None,
            "tracking": product.tracking,
            "available_qty": _get_available_qty(env, product, source_location),
            "uom": {
                "id": product.uom_id.id,
                "name": product.uom_id.name,
            } if product.uom_id else None,
        }
        if van_op_type == "unload":
            item["scrap_qty"] = _get_available_qty(env, product, van_scrap_location) if van_scrap_location else 0.0
        result.append(item)
    return result



def serialize_product_lots(env, payload, product_id):
    employee, distributor, source_location = get_employee_transfer_context(env, payload)
    product = _get_product(env, product_id)
    van_op_type = payload.get("van_operation_type") or "load"

    if van_op_type == "unload":
        van_scrap_location = env["stock.location"].sudo().search([
            ("ss_location_type", "=", "van_loading"),
            ("scrap_location", "=", True),
            ("ss_employee_id", "=", employee.id),
            ("ss_distributor_id", "=", distributor.id),
            ("active", "=", True),
        ], limit=1)

        # Query fresh quants
        fresh_quants = env["stock.quant"].sudo().search([
            ("product_id", "=", product.id),
            ("location_id", "=", source_location.id),
            ("lot_id", "!=", False),
        ])

        # Query scrap quants
        scrap_quants = env["stock.quant"].sudo().search([
            ("product_id", "=", product.id),
            ("location_id", "=", van_scrap_location.id),
            ("lot_id", "!=", False),
        ]) if van_scrap_location else env["stock.quant"].sudo()

        # Group and merge by lot
        lots_dict = {}
        for q in fresh_quants:
            lid = q.lot_id.id
            if lid not in lots_dict:
                lots_dict[lid] = {
                    "lot_id": lid,
                    "lot_name": q.lot_id.name,
                    "available_qty": q.available_quantity,
                    "scrap_qty": 0.0,
                    "quantity": q.quantity,
                    "reserved_quantity": q.reserved_quantity,
                    "uom": {
                        "id": q.product_uom_id.id,
                        "name": q.product_uom_id.name,
                    } if q.product_uom_id else None,
                    "location": _serialize_location(q.location_id),
                }
            else:
                lots_dict[lid]["available_qty"] += q.available_quantity
                lots_dict[lid]["quantity"] += q.quantity
                lots_dict[lid]["reserved_quantity"] += q.reserved_quantity

        for q in scrap_quants:
            lid = q.lot_id.id
            if lid not in lots_dict:
                lots_dict[lid] = {
                    "lot_id": lid,
                    "lot_name": q.lot_id.name,
                    "available_qty": 0.0,
                    "scrap_qty": q.available_quantity,
                    "quantity": q.quantity,
                    "reserved_quantity": q.reserved_quantity,
                    "uom": {
                        "id": q.product_uom_id.id,
                        "name": q.product_uom_id.name,
                    } if q.product_uom_id else None,
                    "location": _serialize_location(q.location_id),
                }
            else:
                lots_dict[lid]["scrap_qty"] += q.available_quantity
                lots_dict[lid]["quantity"] += q.quantity
                lots_dict[lid]["reserved_quantity"] += q.reserved_quantity

        return {
            "product": _serialize_product(product),
            "source_location": _serialize_location(source_location),
            "data": list(lots_dict.values()),
        }

    else:
        domain = [
            ("product_id", "=", product.id),
            ("location_id", "=", source_location.id),
            ("lot_id", "!=", False),
        ]
        if source_location.ss_location_type != "van_loading":
            domain.append(("location_id.ss_location_type", "!=", "van_loading"))

        quants = env["stock.quant"].sudo().search(domain, order="lot_id")
        
        lots_dict = {}
        for q in quants:
            lid = q.lot_id.id
            if lid not in lots_dict:
                lots_dict[lid] = {
                    "lot_id": lid,
                    "lot_name": q.lot_id.name,
                    "available_qty": q.available_quantity,
                    "scrap_qty": 0.0,
                    "quantity": q.quantity,
                    "reserved_quantity": q.reserved_quantity,
                    "uom": {
                        "id": q.product_uom_id.id,
                        "name": q.product_uom_id.name,
                    } if q.product_uom_id else None,
                    "location": _serialize_location(q.location_id),
                }
            else:
                lots_dict[lid]["available_qty"] += q.available_quantity
                lots_dict[lid]["quantity"] += q.quantity
                lots_dict[lid]["reserved_quantity"] += q.reserved_quantity

        final_lots = [
            data for data in lots_dict.values()
            if data["available_qty"] > 0
        ]

        return {
            "product": _serialize_product(product),
            "source_location": _serialize_location(source_location),
            "data": final_lots,
        }


def build_virtual_transfer_domain(env, payload):
    employee = _get_employee(env, payload.get("employee_id"))
    dist_id = payload.get("distributor_id")
    van_operation_type = payload.get("van_operation_type") or "all"

    p_ids = []
    p_type_load = env.ref("meta_ss_transfer.picking_type_virtual_location_transfer", raise_if_not_found=False)
    p_type_unload = env.ref("meta_ss_transfer.picking_type_van_unload_transfer", raise_if_not_found=False)
    
    if van_operation_type == "load" and p_type_load:
        p_ids = [p_type_load.id]
    elif van_operation_type == "unload" and p_type_unload:
        p_ids = [p_type_unload.id]
    else:
        p_ids = [pt.id for pt in (p_type_load, p_type_unload) if pt]

    domain = [
        ("picking_type_id", "in", p_ids),
        ("ss_destination_location_id.ss_location_type", "=", "van_loading"),
        ("so_employee_id", "child_of", employee.id),
    ]
    if dist_id:
        distributor = env["res.partner"].sudo().browse(int(dist_id)).exists()
        domain.append(("ss_distributor_id", "=", distributor.id))

    destination_id = payload.get("destination_location_id")
    if destination_id:
        domain.append(("ss_destination_location_id", "=", _get_integer_id(destination_id, "destination_location_id")))

    assigned_employee_id = payload.get("assigned_employee_id")
    if assigned_employee_id:
        domain.append(("ss_destination_location_id.ss_employee_id", "child_of", _get_integer_id(assigned_employee_id, "assigned_employee_id")))

    state = payload.get("state")
    if state and state != "all":
        domain.append(("state", "=", str(state)))
        
    if van_operation_type and van_operation_type != "all":
        domain.append(("van_operation_type", "=", str(van_operation_type)))

    date = payload.get("date") or payload.get("scheduled_date")
    if date:
        date = str(date)
        domain.append(("scheduled_date", ">=", "%s 00:00:00" % date))
        domain.append(("scheduled_date", "<=", "%s 23:59:59" % date))

    search = (payload.get("search") or "").strip()
    if search:
        domain = expression.AND([
            domain,
            expression.OR([
                [("name", "ilike", search)],
                [("origin", "ilike", search)],
                [("ss_destination_location_id.name", "ilike", search)],
            ]),
        ])
    return domain


def create_virtual_transfer(env, payload):
    employee, distributor, source_location = get_employee_transfer_context(env, payload)
    destination = _get_destination_location(env, payload, employee, distributor)
    van_op_type = payload.get("van_operation_type") or "load"
    picking_type = get_virtual_transfer_picking_type(env, van_op_type)
    lines = payload.get("lines") or payload.get("move_lines") or []
    if not isinstance(lines, list) or not lines:
        raise ValidationError("'lines' must be a non-empty list.")

    if van_op_type == "unload":
        fresh_lines_data = []
        for line in lines:
            pid = line.get("product_id")
            fresh_qty = _get_float(line.get("fresh_qty") if "fresh_qty" in line else line.get("quantity") or 0.0, "fresh qty")
            scrap_qty = _get_float(line.get("scrap_qty") or 0.0, "scrap qty")
            
            lot_lines = line.get("lot_lines") or []
            mapped_lots = []
            for l in lot_lines:
                lot_id = l.get("lot_id")
                l_fresh = _get_float(l.get("fresh_qty") if "fresh_qty" in l else l.get("quantity") or 0.0, "lot fresh qty")
                l_scrap = _get_float(l.get("scrap_qty") or 0.0, "lot scrap qty")
                mapped_lots.append({
                    "lot_id": lot_id,
                    "quantity": l_fresh,
                    "ss_scrap_qty": l_scrap,
                })
            
            fresh_lines_data.append({
                "product_id": pid,
                "quantity": fresh_qty,
                "ss_scrap_qty": scrap_qty,
                "lot_lines": mapped_lots,
            })
            
        prepared_lines = _prepare_transfer_lines(env, fresh_lines_data, source_location)
        for pl in prepared_lines:
            inp = next((i for i in fresh_lines_data if i["product_id"] == pl["product"].id), None)
            if inp:
                pl["ss_scrap_qty"] = inp["ss_scrap_qty"]
                for lot_line in pl.get("lot_lines", []):
                    inp_lot = next((il for il in inp.get("lot_lines", []) if il["lot_id"] == lot_line["lot"].id), None)
                    if inp_lot:
                        lot_line["ss_scrap_qty"] = inp_lot["ss_scrap_qty"]

        _validate_requested_quantities(env, prepared_lines, source_location)

        picking = env["stock.picking"].sudo().create({
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": distributor.property_stock_customer.id,
            "ss_distributor_id": distributor.id,
            "ss_destination_location_id": source_location.id,
            "origin": "Mobile Van Unload Transfer",
            "van_operation_type": "unload",
            "ss_transfer_type": "unload",
            "so_employee_id": employee.id,
            "ss_picking_type": "secondary",
            "ss_transfer_category": "delivery",
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "name": item["product"].display_name,
                        "product_id": item["product"].id,
                        "product_uom_qty": item["quantity"],
                        "ss_scrap_qty": item.get("ss_scrap_qty", 0.0),
                        "product_uom": item["uom"].id,
                        "location_id": source_location.id,
                        "location_dest_id": distributor.property_stock_customer.id,
                    },
                )
                for item in prepared_lines
            ],
        })
        picking.action_confirm()

        for move in picking.move_ids.filtered(lambda item: item.state not in ("cancel", "done")):
            item = next(
                (p for p in prepared_lines if p["product"].id == move.product_id.id),
                None
            )
            if not item:
                continue
            _apply_move_lines(env, picking, move, item)

        return picking

    else:
        prepared_lines = _prepare_transfer_lines(env, lines, source_location)
        _validate_requested_quantities(env, prepared_lines, source_location)

        picking = env["stock.picking"].sudo().create({
            "picking_type_id": picking_type.id,
            "location_id": source_location.id,
            "location_dest_id": destination.id,
            "ss_distributor_id": distributor.id,
            "ss_destination_location_id": destination.id,
            "origin": "Mobile Van Loading Transfer",
            "van_operation_type": "load",
            "ss_transfer_type": "load",
            "so_employee_id": employee.id,
            "ss_picking_type": "secondary",
            "ss_transfer_category": "delivery",
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "name": item["product"].display_name,
                        "product_id": item["product"].id,
                        "product_uom_qty": item["quantity"],
                        "product_uom": item["uom"].id,
                        "location_id": source_location.id,
                        "location_dest_id": destination.id,
                    },
                )
                for item in prepared_lines
            ],
        })
        picking.action_confirm()

        for move in picking.move_ids.filtered(lambda item: item.state not in ("cancel", "done")):
            item = next(
                (p for p in prepared_lines if p["product"].id == move.product_id.id),
                None
            )
            if not item:
                continue
            _apply_move_lines(env, picking, move, item)

        return picking


def update_virtual_transfer(env, transfer_id, payload):
    picking = get_virtual_transfer_for_employee(env, transfer_id, payload)
    if picking.state in ("done", "cancel"):
        raise ValidationError("Cannot update a virtual transfer in its current state.")

    employee, distributor, source_location = get_employee_transfer_context(env, payload)
    destination = _get_destination_location(env, payload, employee, distributor)
    van_op_type = payload.get("van_operation_type") or "load"
    
    lines = payload.get("lines") or payload.get("move_lines") or []
    if not isinstance(lines, list) or not lines:
        raise ValidationError("'lines' must be a non-empty list.")

    if van_op_type == "unload":
        fresh_lines_data = []
        for line in lines:
            pid = line.get("product_id")
            fresh_qty = _get_float(line.get("fresh_qty") if "fresh_qty" in line else line.get("quantity") or 0.0, "fresh qty")
            scrap_qty = _get_float(line.get("scrap_qty") or 0.0, "scrap qty")
            
            lot_lines = line.get("lot_lines") or []
            mapped_lots = []
            for l in lot_lines:
                lot_id = l.get("lot_id")
                l_fresh = _get_float(l.get("fresh_qty") if "fresh_qty" in l else l.get("quantity") or 0.0, "lot fresh qty")
                l_scrap = _get_float(l.get("scrap_qty") or 0.0, "lot scrap qty")
                mapped_lots.append({
                    "lot_id": lot_id,
                    "quantity": l_fresh,
                    "ss_scrap_qty": l_scrap,
                })
            
            fresh_lines_data.append({
                "product_id": pid,
                "quantity": fresh_qty,
                "ss_scrap_qty": scrap_qty,
                "lot_lines": mapped_lots,
            })
            
        prepared_lines = _prepare_transfer_lines(env, fresh_lines_data, source_location)
        for pl in prepared_lines:
            inp = next((i for i in fresh_lines_data if i["product_id"] == pl["product"].id), None)
            if inp:
                pl["ss_scrap_qty"] = inp["ss_scrap_qty"]
                for lot_line in pl.get("lot_lines", []):
                    inp_lot = next((il for il in inp.get("lot_lines", []) if il["lot_id"] == lot_line["lot"].id), None)
                    if inp_lot:
                        lot_line["ss_scrap_qty"] = inp_lot["ss_scrap_qty"]

        _validate_requested_quantities(env, prepared_lines, source_location)

        # Cancel existing moves
        if picking.state != "draft":
            picking.move_ids._action_cancel()
        try:
            picking.move_ids.unlink()
        except Exception:
            pass

        picking.write({
            "location_id": source_location.id,
            "location_dest_id": distributor.property_stock_customer.id,
            "ss_distributor_id": distributor.id,
            "ss_destination_location_id": source_location.id,
            "van_operation_type": "unload",
            "ss_transfer_type": "unload",
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "name": item["product"].display_name,
                        "product_id": item["product"].id,
                        "product_uom_qty": item["quantity"],
                        "ss_scrap_qty": item.get("ss_scrap_qty", 0.0),
                        "product_uom": item["uom"].id,
                        "location_id": source_location.id,
                        "location_dest_id": distributor.property_stock_customer.id,
                    },
                )
                for item in prepared_lines
            ],
        })
        picking.action_confirm()

        for move in picking.move_ids.filtered(lambda item: item.state not in ("cancel", "done")):
            item = next(
                (p for p in prepared_lines if p["product"].id == move.product_id.id),
                None
            )
            if not item:
                continue
            _apply_move_lines(env, picking, move, item)

    else:
        prepared_lines = _prepare_transfer_lines(env, lines, source_location)
        _validate_requested_quantities(env, prepared_lines, source_location)

        # Cancel existing moves
        if picking.state != "draft":
            picking.move_ids._action_cancel()
        try:
            picking.move_ids.unlink()
        except Exception:
            pass

        picking.write({
            "location_id": source_location.id,
            "location_dest_id": destination.id,
            "ss_distributor_id": distributor.id,
            "ss_destination_location_id": destination.id,
            "van_operation_type": "load",
            "ss_transfer_type": "load",
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "name": item["product"].display_name,
                        "product_id": item["product"].id,
                        "product_uom_qty": item["quantity"],
                        "product_uom": item["uom"].id,
                        "location_id": source_location.id,
                        "location_dest_id": destination.id,
                    },
                )
                for item in prepared_lines
            ],
        })
        picking.action_confirm()

        for move in picking.move_ids.filtered(lambda item: item.state not in ("cancel", "done")):
            item = next(
                (p for p in prepared_lines if p["product"].id == move.product_id.id),
                None
            )
            if not item:
                continue
            _apply_move_lines(env, picking, move, item)

    return picking


def get_virtual_transfer_for_employee(env, transfer_id, payload):
    if not transfer_id:
        raise ValidationError("'transfer_id' is required.")
    try:
        transfer_id = int(transfer_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'transfer_id' must be a valid integer id.") from exc

    domain = build_virtual_transfer_domain(env, payload)
    domain.append(("id", "=", transfer_id))
    picking = env["stock.picking"].sudo().search(domain, limit=1)
    if not picking:
        raise ValidationError("Virtual transfer was not found for this employee.")
    return picking


def validate_virtual_transfer(env, transfer_id, payload):
    picking = get_virtual_transfer_for_employee(env, transfer_id, payload)
    if picking.state in ("done", "cancel"):
        raise ValidationError("This virtual transfer cannot be validated in its current state.")

    if picking.state == "draft":
        picking.action_confirm()

    for move in picking.move_ids.filtered(lambda item: item.state not in ("done", "cancel")):
        if float_is_zero(move.quantity, precision_rounding=move.product_uom.rounding):
            if move.product_id.tracking != "none":
                raise ValidationError(
                    "Lot allocation is required before validating product '%s'."
                    % move.product_id.display_name
                )
            _create_move_line(env, picking, move, move.product_uom_qty)
            move.write({"picked": True})
            move.move_line_ids.write({"picked": True})

    result = picking.with_context(
        skip_backorder=True,
        button_validate_picking_ids=picking.ids,
    ).button_validate()
    return picking, result


def cancel_virtual_transfer(env, transfer_id, payload):
    picking = get_virtual_transfer_for_employee(env, transfer_id, payload)
    if picking.state == "done":
        raise ValidationError("Done virtual transfers cannot be cancelled.")
    if picking.state != "cancel":
        picking.action_cancel()
    return picking


def serialize_virtual_transfer(picking):
    picking = picking.sudo()
    return {
        "id": picking.id,
        "name": picking.name,
        "state": picking.state,
        "van_operation_type": picking.van_operation_type,
        "ss_transfer_category": picking.ss_transfer_category or None,
        "scheduled_date": str(picking.scheduled_date) if picking.scheduled_date else None,
        "origin": picking.origin or None,
        "distributor": _serialize_distributor(picking.ss_distributor_id),
        "source_location": _serialize_location(picking.location_id),
        "destination_location": serialize_van_loading_location(
            picking.ss_destination_location_id or picking.location_dest_id
        ),
        "lines": [_serialize_transfer_move(move) for move in picking.move_ids],
    }


def serialize_van_loading_location(location):
    return {
        "id": location.id,
        "name": location.display_name,
        "usage": location.usage,
        "location_type": location.ss_location_type,
        "employee": _serialize_employee(location.ss_employee_id),
        "distributor": _serialize_distributor(location.ss_distributor_id),
    }


def get_virtual_transfer_pagination(payload):
    return get_pagination(payload)


def _get_destination_location(env, payload, employee, distributor):
    destination_id = payload.get("destination_location_id")
    if not destination_id:
        destinations = _get_employee_van_locations(env, employee, distributor)
        if len(destinations) == 1:
            return destinations[0]
        raise ValidationError("'destination_location_id' is required.")
    try:
        destination_id = int(destination_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'destination_location_id' must be a valid integer id.") from exc

    destination = env["stock.location"].sudo().browse(destination_id).exists()
    if not destination:
        raise ValidationError("Destination location not found.")
    if destination.ss_location_type != "van_loading":
        raise ValidationError("Destination must be a Van Loading Location.")
    logged_in_employee = _get_employee(env, payload.get("employee_id"))
    subordinates = env["hr.employee"].sudo().search([("id", "child_of", logged_in_employee.id)])
    if destination.ss_employee_id not in subordinates:
        raise ValidationError("Destination location is not assigned to you or your subordinates.")
    if not destination.ss_distributor_id:
        raise ValidationError("Destination location has no assigned distributor.")
    return destination


def _get_destination_location_from_payload(env, payload):
    destination_id = payload.get("destination_location_id")
    if not destination_id:
        return env["stock.location"]

    destination_id = _get_integer_id(destination_id, "destination_location_id")
    destination = env["stock.location"].sudo().browse(destination_id).exists()
    if not destination:
        raise ValidationError("Destination location not found.")
    if destination.ss_location_type != "van_loading":
        raise ValidationError("Destination must be a Van Loading Location.")
    if not destination.ss_employee_id:
        raise ValidationError("Destination location has no assigned employee.")
    if not destination.ss_distributor_id:
        raise ValidationError("Destination location has no assigned distributor.")
    return destination


def _get_prepare_van_locations(env, employee, distributor):
    domain = [
        ("ss_location_type", "=", "van_loading"),
        ("scrap_location", "=", False),
        ("active", "=", True),
        ("ss_employee_id", "child_of", employee.id),
    ]
    return env["stock.location"].sudo().search(domain, order="name")


def _get_employee_van_locations(env, employee, distributor):
    return env["stock.location"].sudo().search([
        ("ss_location_type", "=", "van_loading"),
        ("ss_employee_id", "child_of", employee.id),
        ("scrap_location", "=", False),
        ("active", "=", True),
    ], order="name")


def _prepare_transfer_lines(env, lines, source_location):
    prepared = []
    seen_products = set()
    for index, line in enumerate(lines, start=1):
        if not isinstance(line, dict):
            raise ValidationError("Each transfer line must be an object.")

        product = _get_product(env, line.get("product_id"))
        if product.id in seen_products:
            raise ValidationError("Duplicate product lines are not allowed.")
        seen_products.add(product.id)

        qty_val = line.get("quantity", line.get("product_uom_qty"))
        scrap_val = line.get("ss_scrap_qty") or line.get("scrap_qty") or 0.0
        if scrap_val > 0.0:
            quantity = _get_non_negative_float(qty_val or 0.0, "quantity")
        else:
            quantity = _get_positive_float(qty_val, "quantity")
        uom = _get_product_uom(env, line.get("uom_id"), product) if line.get("uom_id") else product.uom_id
        if not uom:
            raise ValidationError("Product '%s' has no unit of measure." % product.display_name)

        lot_lines = _prepare_lot_lines(env, product, quantity, line.get("lot_lines") or [], source_location)
        prepared.append({
            "sequence": index * 10,
            "product": product,
            "quantity": quantity,
            "uom": uom,
            "lot_lines": lot_lines,
            "available_qty": _get_available_qty(env, product, source_location),
        })
    return prepared


def _prepare_lot_lines(env, product, quantity, lot_lines, source_location):
    if product.tracking == "none":
        return []
    if not isinstance(lot_lines, list) or not lot_lines:
        from odoo.addons.meta_ss_rest_api.utils.helpers import _auto_assign_lots
        try:
            assigned_lots = _auto_assign_lots(env, product, quantity, source_location)
            lot_lines = [{"lot_id": item["lot_id"], "quantity": item["quantity"]} for item in assigned_lots]
        except ValidationError as e:
            raise ValidationError("Auto-assigning FIFO lots failed: %s" % e.message)

    total = 0.0
    prepared = []
    for lot_line in lot_lines:
        if not isinstance(lot_line, dict):
            raise ValidationError("Each lot line must be an object.")
        lot = _get_lot(env, product, lot_line.get("lot_id"))
        
        lot_scrap = _get_non_negative_float(lot_line.get("ss_scrap_qty") or lot_line.get("scrap_qty") or 0.0, "lot scrap quantity")
        if lot_scrap > 0.0:
            lot_qty = _get_non_negative_float(lot_line.get("quantity") or 0.0, "lot quantity")
        else:
            lot_qty = _get_positive_float(lot_line.get("quantity"), "lot quantity")
            
        if product.tracking == "serial" and float_compare(
            lot_qty, 1.0, precision_rounding=product.uom_id.rounding
        ) > 0:
            raise ValidationError("Serial-tracked products must move one unit per serial.")
        total += lot_qty
        prepared.append({"lot": lot, "quantity": lot_qty})

    if float_compare(total, quantity, precision_rounding=product.uom_id.rounding) != 0:
        raise ValidationError("Total lot quantity must match transfer quantity.")
    return prepared


def _validate_requested_quantities(env, prepared_lines, source_location):
    is_unload = source_location.ss_location_type == "van_loading" and not source_location.scrap_location
    van_scrap_location = env["stock.location"]
    if is_unload:
        van_scrap_location = env["stock.location"].sudo().search([
            ("ss_location_type", "=", "van_loading"),
            ("scrap_location", "=", True),
            ("ss_employee_id", "=", source_location.ss_employee_id.id),
            ("ss_distributor_id", "=", source_location.ss_distributor_id.id),
            ("active", "=", True),
        ], limit=1)

    for item in prepared_lines:
        if float_compare(
            item["quantity"],
            item["available_qty"],
            precision_rounding=item["uom"].rounding,
        ) > 0:
            raise ValidationError(
                "Requested quantity exceeds available quantity for product '%s'."
                % item["product"].display_name
            )

        scrap_qty_requested = item.get("ss_scrap_qty", 0.0)
        if scrap_qty_requested > 0.0:
            if not van_scrap_location:
                raise ValidationError("Van Scrap Location not configured.")
            scrap_available = _get_available_qty(env, item["product"], van_scrap_location)
            if float_compare(
                scrap_qty_requested,
                scrap_available,
                precision_rounding=item["uom"].rounding,
            ) > 0:
                raise ValidationError(
                    "Requested scrap quantity exceeds available scrap quantity for product '%s'. (Requested: %s, Available: %s)"
                    % (item["product"].display_name, scrap_qty_requested, scrap_available)
                )

        for lot_line in item["lot_lines"]:
            lot_qty = _get_lot_available_qty(env, item["product"], lot_line["lot"], source_location)
            if float_compare(
                lot_line["quantity"],
                lot_qty,
                precision_rounding=item["uom"].rounding,
            ) > 0:
                raise ValidationError(
                    "Requested lot quantity exceeds available quantity for lot '%s'."
                    % lot_line["lot"].name
                )

            lot_scrap_qty_requested = lot_line.get("ss_scrap_qty", 0.0)
            if lot_scrap_qty_requested > 0.0:
                if not van_scrap_location:
                    raise ValidationError("Van Scrap Location not configured.")
                lot_scrap_qty = _get_lot_available_qty(env, item["product"], lot_line["lot"], van_scrap_location)
                if float_compare(
                    lot_scrap_qty_requested,
                    lot_scrap_qty,
                    precision_rounding=item["uom"].rounding,
                ) > 0:
                    raise ValidationError(
                        "Requested scrap lot quantity exceeds available scrap quantity for lot '%s'."
                        % lot_line["lot"].name
                    )


def _apply_move_lines(env, picking, move, item):
    move.move_line_ids.unlink()
    if item["product"].tracking == "none":
        _create_move_line(env, picking, move, item["quantity"])
        if item.get("ss_scrap_qty"):
            move.move_line_ids.write({"ss_scrap_qty": item["ss_scrap_qty"]})
    else:
        for lot_line in item["lot_lines"]:
            _create_move_line(env, picking, move, lot_line["quantity"], lot=lot_line["lot"])
            if lot_line.get("ss_scrap_qty"):
                ml = move.move_line_ids.filtered(lambda l: l.lot_id == lot_line["lot"])
                if ml:
                    ml.write({"ss_scrap_qty": lot_line["ss_scrap_qty"]})
    move.write({"picked": True})
    move.move_line_ids.write({"picked": True})


def _get_available_product_ids(env, source_location):
    domain = [
        ("location_id", "=", source_location.id),
    ]
    if source_location.ss_location_type != "van_loading":
        domain.append(("location_id.ss_location_type", "!=", "van_loading"))

    quants = env["stock.quant"].sudo().search(domain)
    
    from collections import defaultdict
    prod_avail = defaultdict(float)
    for q in quants:
        prod_avail[q.product_id.id] += q.available_quantity
        
    return [pid for pid, qty in prod_avail.items() if qty > 0]


def _get_available_qty(env, product, source_location):
    domain = [
        ("product_id", "=", product.id),
        ("location_id", "=", source_location.id),
    ]
    if source_location.ss_location_type != "van_loading":
        domain.append(("location_id.ss_location_type", "!=", "van_loading"))

    quants = env["stock.quant"].sudo().search(domain)
    return sum(quants.mapped("available_quantity"))


def _get_lot_available_qty(env, product, lot, source_location):
    domain = [
        ("product_id", "=", product.id),
        ("lot_id", "=", lot.id),
        ("location_id", "=", source_location.id),
    ]
    if source_location.ss_location_type != "van_loading":
        domain.append(("location_id.ss_location_type", "!=", "van_loading"))

    quants = env["stock.quant"].sudo().search(domain)
    return sum(quants.mapped("available_quantity"))


def _get_product(env, product_id):
    if not product_id:
        raise ValidationError("'product_id' is required.")
    try:
        product_id = int(product_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'product_id' must be a valid integer id.") from exc
    product = env["product.product"].sudo().browse(product_id).exists()
    if not product:
        raise ValidationError("Product not found.")
    if product.type == "service":
        raise ValidationError("Service products cannot be transferred.")
    return product


def _get_product_uom(env, uom_id, product):
    try:
        uom_id = int(uom_id)
    except (TypeError, ValueError) as exc:
        raise ValidationError("'uom_id' must be a valid integer id.") from exc
    uom = env["uom.uom"].sudo().browse(uom_id).exists()
    if not uom:
        raise ValidationError("Unit of measure not found.")
    if uom.category_id != product.uom_id.category_id:
        raise ValidationError("Unit of measure does not match product '%s'." % product.display_name)
    return uom


def _serialize_employee(employee):
    return {
        "id": employee.id,
        "name": employee.name,
    } if employee else None


def _serialize_distributor(distributor):
    return {
        "id": distributor.id,
        "name": distributor.name,
        "customer_stock_location": _serialize_location(distributor.property_stock_customer),
    } if distributor else None


def _serialize_location(location):
    return {
        "id": location.id,
        "name": location.display_name,
        "usage": location.usage,
    } if location else None


def _serialize_product(product):
    return {
        "id": product.id,
        "name": product.display_name,
        "default_code": product.default_code or None,
        "tracking": product.tracking,
        "uom": {
            "id": product.uom_id.id,
            "name": product.uom_id.name,
        } if product.uom_id else None,
    } if product else None


def _serialize_transfer_move(move):
    return {
        "move_id": move.id,
        "state": move.state,
        "product": _serialize_product(move.product_id),
        "demand_qty": move.product_uom_qty,
        "quantity": move.quantity,
        "scrap_qty": move.ss_scrap_qty,
        "uom": {
            "id": move.product_uom.id,
            "name": move.product_uom.name,
        } if move.product_uom else None,
        "lot_lines": [
            {
                "move_line_id": line.id,
                "lot": {
                    "id": line.lot_id.id,
                    "name": line.lot_id.name,
                } if line.lot_id else None,
                "quantity": line.quantity,
                "scrap_qty": line.ss_scrap_qty,
                "source_location": _serialize_location(line.location_id),
                "destination_location": _serialize_location(line.location_dest_id),
            }
            for line in move.move_line_ids
        ],
    }

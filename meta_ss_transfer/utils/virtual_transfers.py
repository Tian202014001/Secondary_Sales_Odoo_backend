# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero

from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination
from odoo.addons.meta_ss_rest_api.utils.helpers import _create_move_line, _get_float, _get_positive_float, _get_integer_id, _get_employee, _get_lot


def get_virtual_transfer_picking_type(env):
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
        distributor = employee.distributor_contact_id.sudo()
    if not distributor:
        raise ValidationError("Select a Van Loading Location before loading transfer stock.")
    if distributor.customer_type != "distributor":
        raise ValidationError("The employee's assigned contact is not a distributor.")
    source_location = distributor.property_stock_customer
    if not source_location:
        raise ValidationError("The assigned distributor has no customer stock location.")
    return employee, distributor, source_location


def serialize_virtual_transfer_prepare(env, payload):
    employee = _get_employee(env, payload.get("employee_id"))
    distributor = employee.distributor_contact_id.sudo()
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


def serialize_transfer_products(env, products, source_location):
    return [
        {
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
        for product in products
    ]


def serialize_product_lots(env, payload, product_id):
    _employee, _distributor, source_location = get_employee_transfer_context(env, payload)
    product = _get_product(env, product_id)
    domain = [
        ("product_id", "=", product.id),
        ("location_id", "child_of", source_location.id),
        ("available_quantity", ">", 0),
        ("lot_id", "!=", False),
    ]
    if source_location.ss_location_type != "van_loading":
        domain.append(("location_id.ss_location_type", "!=", "van_loading"))

    quants = env["stock.quant"].sudo().search(domain, order="lot_id")
    return {
        "product": _serialize_product(product),
        "source_location": _serialize_location(source_location),
        "data": [
            {
                "lot_id": quant.lot_id.id,
                "lot_name": quant.lot_id.name,
                "available_qty": quant.available_quantity,
                "quantity": quant.quantity,
                "reserved_quantity": quant.reserved_quantity,
                "uom": {
                    "id": quant.product_uom_id.id,
                    "name": quant.product_uom_id.name,
                } if quant.product_uom_id else None,
                "location": _serialize_location(quant.location_id),
            }
            for quant in quants
        ],
    }


def build_virtual_transfer_domain(env, payload):
    employee = _get_employee(env, payload.get("employee_id"))
    distributor = employee.distributor_contact_id.sudo()
    picking_type = get_virtual_transfer_picking_type(env)
    domain = [
        ("picking_type_id", "=", picking_type.id),
        ("ss_destination_location_id.ss_location_type", "=", "van_loading"),
    ]
    if distributor:
        domain.append(("ss_distributor_id", "=", distributor.id))
        domain.append(("ss_destination_location_id.ss_employee_id", "=", employee.id))

    destination_id = payload.get("destination_location_id")
    if destination_id:
        domain.append(("ss_destination_location_id", "=", _get_integer_id(destination_id, "destination_location_id")))

    assigned_employee_id = payload.get("assigned_employee_id")
    if assigned_employee_id:
        domain.append(("ss_destination_location_id.ss_employee_id", "=", _get_integer_id(assigned_employee_id, "assigned_employee_id")))

    state = payload.get("state")
    if state and state != "all":
        domain.append(("state", "=", str(state)))

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
    picking_type = get_virtual_transfer_picking_type(env)
    lines = payload.get("lines") or payload.get("move_lines") or []
    if not isinstance(lines, list) or not lines:
        raise ValidationError("'lines' must be a non-empty list.")

    prepared_lines = _prepare_transfer_lines(env, lines, source_location)
    _validate_requested_quantities(env, prepared_lines, source_location)

    picking = env["stock.picking"].sudo().create({
        "picking_type_id": picking_type.id,
        "location_id": source_location.id,
        "location_dest_id": destination.id,
        "ss_distributor_id": distributor.id,
        "ss_destination_location_id": destination.id,
        "origin": "Mobile Van Loading Transfer",
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
    if destination.ss_employee_id != employee:
        raise ValidationError("Destination location is not assigned to this employee.")
    if destination.ss_distributor_id != distributor:
        raise ValidationError("Destination location is not assigned to this distributor.")
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
    ]
    if distributor:
        domain.append(("ss_distributor_id", "=", distributor.id))
        if employee.distributor_contact_id:
            domain.append(("ss_employee_id", "=", employee.id))
    return env["stock.location"].sudo().search(domain, order="name")


def _get_employee_van_locations(env, employee, distributor):
    return env["stock.location"].sudo().search([
        ("ss_location_type", "=", "van_loading"),
        ("ss_employee_id", "=", employee.id),
        ("ss_distributor_id", "=", distributor.id),
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

        quantity = _get_positive_float(line.get("quantity", line.get("product_uom_qty")), "quantity")
        uom = _get_product_uom(env, line.get("uom_id"), product) if line.get("uom_id") else product.uom_id
        if not uom:
            raise ValidationError("Product '%s' has no unit of measure." % product.display_name)

        lot_lines = _prepare_lot_lines(env, product, quantity, line.get("lot_lines") or [])
        prepared.append({
            "sequence": index * 10,
            "product": product,
            "quantity": quantity,
            "uom": uom,
            "lot_lines": lot_lines,
            "available_qty": _get_available_qty(env, product, source_location),
        })
    return prepared


def _prepare_lot_lines(env, product, quantity, lot_lines):
    if product.tracking == "none":
        return []
    if not isinstance(lot_lines, list) or not lot_lines:
        raise ValidationError("Lot allocation is required for product '%s'." % product.display_name)

    total = 0.0
    prepared = []
    for lot_line in lot_lines:
        if not isinstance(lot_line, dict):
            raise ValidationError("Each lot line must be an object.")
        lot = _get_lot(env, product, lot_line.get("lot_id"))
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


def _apply_move_lines(env, picking, move, item):
    move.move_line_ids.unlink()
    if item["product"].tracking == "none":
        _create_move_line(env, picking, move, item["quantity"])
    else:
        for lot_line in item["lot_lines"]:
            _create_move_line(env, picking, move, lot_line["quantity"], lot=lot_line["lot"])
    move.write({"picked": True})
    move.move_line_ids.write({"picked": True})


def _get_available_product_ids(env, source_location):
    domain = [
        ("location_id", "child_of", source_location.id),
        ("available_quantity", ">", 0),
    ]
    if source_location.ss_location_type != "van_loading":
        domain.append(("location_id.ss_location_type", "!=", "van_loading"))

    quants = env["stock.quant"].sudo().search(domain)
    return list(set(quants.mapped("product_id").ids))


def _get_available_qty(env, product, source_location):
    domain = [
        ("product_id", "=", product.id),
        ("location_id", "child_of", source_location.id),
        ("available_quantity", ">", 0),
    ]
    if source_location.ss_location_type != "van_loading":
        domain.append(("location_id.ss_location_type", "!=", "van_loading"))

    quants = env["stock.quant"].sudo().search(domain)
    return sum(quants.mapped("available_quantity"))


def _get_lot_available_qty(env, product, lot, source_location):
    domain = [
        ("product_id", "=", product.id),
        ("lot_id", "=", lot.id),
        ("location_id", "child_of", source_location.id),
        ("available_quantity", ">", 0),
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
                "source_location": _serialize_location(line.location_id),
                "destination_location": _serialize_location(line.location_dest_id),
            }
            for line in move.move_line_ids
        ],
    }

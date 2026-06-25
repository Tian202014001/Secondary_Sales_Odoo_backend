# -*- coding: utf-8 -*-

from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools.float_utils import float_compare, float_is_zero

from odoo.addons.meta_ss_rest_api.utils.routes import get_pagination
from odoo.addons.meta_ss_rest_api.utils.helpers import _create_move_line, _get_positive_float, _get_integer_id, _get_employee, _get_lot


def get_employee_scrap_context(env, payload):
    employee = _get_employee(env, payload.get("employee_id"))
    dist_id = payload.get("distributor_id")
    if dist_id:
        distributor = env["res.partner"].sudo().browse(int(dist_id)).exists()
        if not distributor:
            raise ValidationError("Distributor not found.")
    else:
        distributors = employee.distributor_contact_ids.sudo()
        if not distributors:
            subordinates = env["hr.employee"].sudo().search([("id", "child_of", employee.id)])
            distributors = subordinates.mapped("distributor_contact_ids").sudo()
        
        distributors = distributors.filtered(lambda d: d.customer_type == "distributor")
        
        if len(distributors) == 1:
            distributor = distributors[0]
        elif len(distributors) > 1:
            distributor = distributors[0]
        else:
            raise ValidationError("Employee and subordinates are not assigned to any distributor.")
            
    if distributor.customer_type != "distributor":
        raise ValidationError("The assigned contact is not a distributor.")
        
    # Context override: override employee to the subordinate who owns this distributor
    subordinates = env["hr.employee"].sudo().search([("id", "child_of", employee.id)])
    sub_emp = subordinates.filtered(lambda e: distributor.id in e.distributor_contact_ids.ids)
    if sub_emp:
        employee = sub_emp[0]
        
    source_location = distributor.scrap_location_id
    if not source_location:
        raise ValidationError("The assigned distributor has no scrap location.")
        
    # Get the scrap destination location
    dest_location = env['stock.location'].sudo().search([('scrap_location', '=', True), ('company_id', 'in', [False, env.company.id])], limit=1)
    if not dest_location:
        raise ValidationError("No scrap location found for the company.")
        
    warehouse = env['stock.warehouse'].sudo().search([('company_id', 'in', [False, env.company.id])], limit=1)
    
    return employee, distributor, source_location, dest_location, warehouse


def serialize_scrap_prepare(env, payload):
    employee, distributor, source_location, dest_location, warehouse = get_employee_scrap_context(env, payload)
    
    logged_in_employee = _get_employee(env, payload.get("employee_id"))
    subordinates = env["hr.employee"].sudo().search([("id", "child_of", logged_in_employee.id)])
    allowed_distributors = subordinates.mapped("distributor_contact_ids").filtered(
        lambda d: d.customer_type == "distributor"
    ).sudo()
    
    return {
        "employee": {
            "id": employee.id,
            "name": employee.name,
        },
        "distributor": {
            "id": distributor.id,
            "name": distributor.name,
        },
        "distributors": [
            {"id": d.id, "name": d.name} for d in allowed_distributors
        ],
        "source_location": {
            "id": source_location.id,
            "name": source_location.display_name,
        },
        "destination_location": {
            "id": dest_location.id,
            "name": dest_location.display_name,
        },
        "warehouse": {
            "id": warehouse.id,
            "name": warehouse.name,
        }
    }


def build_scrap_product_domain(env, payload):
    _employee, _distributor, source_location, _dest, _wh = get_employee_scrap_context(env, payload)
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


def serialize_scrap_products(env, products, source_location):
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


def serialize_scrap_product_lots(env, payload, product_id):
    _employee, _distributor, source_location, _dest, _wh = get_employee_scrap_context(env, payload)
    product = _get_product(env, product_id)
    domain = [
        ("product_id", "=", product.id),
        ("location_id", "child_of", source_location.id),
        ("available_quantity", ">", 0),
        ("lot_id", "!=", False),
    ]

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

def build_scrap_domain(env, payload):
    employee_id = payload.get("employee_id")
    dist_id = payload.get("distributor_id")
    
    if dist_id:
        distributor = env["res.partner"].sudo().browse(int(dist_id)).exists()
        distributor_ids = [distributor.id]
    elif employee_id:
        # Hierarchy check: get all subordinates
        subordinates = env["hr.employee"].sudo().search([("id", "child_of", int(employee_id))])
        distributor_ids = subordinates.mapped("distributor_contact_ids").ids
    else:
        distributor_ids = []

    warehouse = env['stock.warehouse'].sudo().search([('company_id', 'in', [False, env.company.id])], limit=1)
    picking_type = warehouse.in_type_id if warehouse else env['stock.picking.type']

    domain = [
        ("picking_type_id", "=", picking_type.id),
        ("location_dest_id.scrap_location", "=", True),
    ]

    picking_type_filter = payload.get("picking_type") or payload.get("type") or payload.get("sale_type")
    if picking_type_filter:
        domain.append(("ss_picking_type", "=", picking_type_filter))
    
    if distributor_ids:
        domain.extend([
            "|",
            ("ss_distributor_id", "in", distributor_ids),
            ("partner_id", "in", distributor_ids)
        ])

    state = payload.get("state")
    if state and state != "all":
        domain.append(("state", "=", str(state)))

    date = payload.get("date") or payload.get("scheduled_date")
    if date:
        date = str(date)
        domain.append(("scheduled_date", ">=", f"{date} 00:00:00"))
        domain.append(("scheduled_date", "<=", f"{date} 23:59:59"))

    search = (payload.get("search") or "").strip()
    if search:
        domain = expression.AND([
            domain,
            expression.OR([
                [("name", "ilike", search)],
                [("origin", "ilike", search)],
            ]),
        ])
    return domain


def serialize_scraps(pickings):
    return [
        {
            "id": picking.id,
            "name": picking.name,
            "state": picking.state,
            "scheduled_date": str(picking.scheduled_date) if picking.scheduled_date else None,
            "origin": picking.origin or None,
            "source_location": _serialize_location(picking.location_id),
            "destination_location": _serialize_location(picking.location_dest_id),
        }
        for picking in pickings.sudo()
    ]


def create_scrap_delivery(env, payload):
    # Step 1: Context Setup
    # Identifies the Source (Distributor's customer location) and Destination (Warehouse)
    employee, distributor, source_location, dest_location, warehouse = get_employee_scrap_context(env, payload)
    
    lines = payload.get("lines") or []
    if not isinstance(lines, list) or not lines:
        raise ValidationError("'lines' must be a non-empty list.")

    # Step 2: Validation
    # strictly checks if those exact products and lots actually exist in the distributor's stock
    prepared_lines = _prepare_transfer_lines(env, lines, source_location)
    _validate_requested_quantities(env, prepared_lines, source_location)

    picking_type = warehouse.in_type_id
    if not picking_type:
        raise ValidationError("No 'Receipts' operation type found for the warehouse.")

    # Step 3: Creating the Draft Transfer
    # Creates the main Odoo transfer record (`stock.picking`). 
    # Inside `move_ids`, it creates a `stock.move` for every product representing general demand.
    # At this moment, the picking is in a Draft state.
    picking = env["stock.picking"].sudo().create({
        "picking_type_id": picking_type.id,
        "location_id": source_location.id,
        "location_dest_id": dest_location.id,
        "partner_id": distributor.id,
        "ss_distributor_id": distributor.id,
        "so_employee_id": employee.id,
        "origin": f"Scrap from {distributor.name}",
        "ss_picking_type": payload.get("picking_type") or payload.get("type") or payload.get("sale_type") or "primary",
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
                    "location_dest_id": dest_location.id,
                },
            )
            for item in prepared_lines
        ],
    })
    
    # Step 4: Confirming the Transfer
    # We call action_confirm() for two reasons:
    # 1. To Allow Lot Assignment: In Odoo, you cannot assign specific lots (Detailed Operations) 
    #    while a transfer is in Draft. Confirming unlocks Odoo's state, allowing us to immediately 
    #    attach the manual Lots the mobile user selected.
    # 2. To Make it Visible: Draft transfers often don't show up in warehouse dashboards. 
    #    This moves it to "Ready" status so backend staff can see it and later "Validate" it.
    picking.action_confirm()

    # Step 5: Assigning the Exact Lots
    # The _apply_move_lines function creates stock.move.line records (Detailed Operations) 
    # underneath each general move. Because the user explicitly selected specific Lots in the app, 
    # this step saves those exact Lots to the transfer.
    for move in picking.move_ids.filtered(lambda m: m.state not in ("cancel", "done")):
        item = next(
            (p for p in prepared_lines if p["product"].id == move.product_id.id),
            None
        )
        if not item:
            continue
        _apply_move_lines(env, picking, move, item)

    return picking


def get_scrap_delivery_for_employee(env, picking_id, payload):
    domain = build_scrap_domain(env, payload)
    domain.append(("id", "=", int(picking_id)))
    picking = env["stock.picking"].sudo().search(domain, limit=1)
    if not picking:
        raise ValidationError("Scrap delivery not found or access denied.")
    return picking


def update_scrap_delivery(env, picking_id, payload):
    picking = get_scrap_delivery_for_employee(env, picking_id, payload)
    if picking.state in ("done", "cancel"):
        raise ValidationError("Cannot update a return delivery in its current state.")

    employee, distributor, source_location, dest_location, warehouse = get_employee_scrap_context(env, payload)

    lines = payload.get("lines") or payload.get("move_lines") or []
    if not isinstance(lines, list) or not lines:
        raise ValidationError("'lines' must be a non-empty list.")

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
        "ss_picking_type": payload.get("picking_type") or payload.get("type") or payload.get("sale_type") or "primary",
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
                    "location_dest_id": dest_location.id,
                },
            )
            for item in prepared_lines
        ],
    })

    picking.action_confirm()

    for move in picking.move_ids.filtered(lambda m: m.state not in ("cancel", "done")):
        item = next(
            (p for p in prepared_lines if p["product"].id == move.product_id.id),
            None
        )
        if not item:
            continue
        _apply_move_lines(env, picking, move, item)

    return picking


def serialize_scrap_delivery(picking):
    picking = picking.sudo()
    return {
        "id": picking.id,
        "name": picking.name,
        "state": picking.state,
        "scheduled_date": str(picking.scheduled_date) if picking.scheduled_date else None,
        "origin": picking.origin or None,
        "distributor": {"id": picking.partner_id.id, "name": picking.partner_id.name} if picking.partner_id else ({"id": picking.ss_distributor_id.id, "name": picking.ss_distributor_id.name} if picking.ss_distributor_id else None),
        "source_location": _serialize_location(picking.location_id),
        "destination_location": _serialize_location(picking.location_dest_id),
        "lines": [_serialize_transfer_move(move) for move in picking.move_ids],
    }


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
    # For incoming receipts, move.move_line_ids might be empty initially.
    # But if there are any, we might need to update them or create new ones.
    if move.move_line_ids:
        move.move_line_ids.unlink()
        
    if item["product"].tracking == "none":
        _create_move_line(env, picking, move, item["quantity"])
    else:
        for lot_line in item["lot_lines"]:
            _create_move_line(env, picking, move, lot_line["quantity"], lot=lot_line["lot"])


def _get_available_product_ids(env, source_location):
    domain = [
        ("location_id", "child_of", source_location.id),
        ("available_quantity", ">", 0),
    ]
    quants = env["stock.quant"].sudo().search(domain)
    return list(set(quants.mapped("product_id").ids))


def _get_available_qty(env, product, source_location):
    domain = [
        ("product_id", "=", product.id),
        ("location_id", "child_of", source_location.id),
        ("available_quantity", ">", 0),
    ]
    quants = env["stock.quant"].sudo().search(domain)
    return sum(quants.mapped("available_quantity"))


def _get_lot_available_qty(env, product, lot, source_location):
    domain = [
        ("product_id", "=", product.id),
        ("lot_id", "=", lot.id),
        ("location_id", "child_of", source_location.id),
        ("available_quantity", ">", 0),
    ]
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

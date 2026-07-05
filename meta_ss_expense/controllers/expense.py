# -*- coding: utf-8 -*-
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import ValidationError, UserError

from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    handle_api_exception,
)


class ExpenseAPI(http.Controller):

    @http.route(f"{API_PREFIX}/hr/expense/categories", type="json", auth="user", methods=["POST"])
    def expense_categories(self, **payload):
        """Fetch categories/products that can be expensed."""
        try:
            _, api_env, _ = get_mobile_api_context(payload)
            
            categories = api_env["product.product"].sudo().search([
                ("can_be_expensed", "=", True)
            ])
            
            data = []
            for cat in categories:
                data.append({
                    "id": cat.id,
                    "name": cat.name or "",
                })
                
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Expense categories fetched successfully.",
                "data": data
            }
        except Exception as e:
            return handle_api_exception(e)

    @http.route(f"{API_PREFIX}/hr/expense/list", type="json", auth="user", methods=["POST"])
    def expense_list(self, **payload):
        """Fetch own or pending approval expenses."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            employee_id = payload.get("employee_id")
            mode = payload.get("mode", "own") # 'own' or 'pending'
            
            if not employee_id:
                raise ValidationError("employee_id is required.")
                
            employee = api_env["hr.employee"].sudo().browse(int(employee_id))
            if not employee.exists():
                raise ValidationError("Employee not found.")

            expenses = api_env["hr.expense"]
            
            if mode == "pending":
                # Find all submitted sheets
                submitted_sheets = api_env["hr.expense.sheet"].sudo().search([
                    ("state", "=", "submit")
                ])
                # Filter sheets where the current user has approval rights
                pending_sheets = submitted_sheets.filtered(lambda s: s.can_approve)
                expenses = pending_sheets.mapped("expense_line_ids")
            else:
                expenses = api_env["hr.expense"].sudo().search([
                    ("employee_id", "=", employee.id)
                ], order="date desc, id desc")

            data = []
            for rec in expenses:
                # Map state to friendly labels
                status_labels = {
                    "draft": "Draft",
                    "reported": "Reported",
                    "submitted": "Pending",
                    "approved": "Approved",
                    "done": "Paid",
                    "refused": "Rejected"
                }
                
                data.append({
                    "id": rec.id,
                    "sheet_id": rec.sheet_id.id if rec.sheet_id else None,
                    "employee_name": rec.employee_id.name or "",
                    "title": rec.name or "",
                    "category": rec.product_id.name or "",
                    "category_id": rec.product_id.id if rec.product_id else None,
                    "amount": float(rec.total_amount_currency or rec.total_amount or 0.0),
                    "date": rec.date.strftime("%Y-%m-%d") if rec.date else "",
                    "status": rec.state or "draft",
                    "status_label": status_labels.get(rec.state, "Draft"),
                    "payment_mode": rec.payment_mode or "own_account",
                    "description": rec.description or "",
                    "can_approve": rec.sheet_id.can_approve if rec.sheet_id else False,
                })

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": f"Expense list ({mode}) fetched successfully.",
                "data": data
            }
        except Exception as e:
            return handle_api_exception(e)

    @http.route(f"{API_PREFIX}/hr/expense/approve", type="json", auth="user", methods=["POST"])
    def expense_approve(self, **payload):
        """Approve an expense sheet."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            sheet_id = payload.get("sheet_id")
            expense_id = payload.get("expense_id")
            
            if not sheet_id and not expense_id:
                raise ValidationError("sheet_id or expense_id is required.")
                
            if sheet_id:
                sheet = api_env["hr.expense.sheet"].sudo().browse(int(sheet_id))
            else:
                expense = api_env["hr.expense"].sudo().browse(int(expense_id))
                if not expense.exists():
                    raise ValidationError("Expense record not found.")
                sheet = expense.sheet_id

            if not sheet or not sheet.exists():
                raise ValidationError("Expense report not found.")
                
            # Perform approval: run security policy check first with API context, then execute action with sudo
            sheet.with_context(mobile_api_user_id=api_env.context.get('mobile_api_user_id'))._check_app_workflow_policy('approve')
            sheet.sudo().action_approve_expense_sheets()
            
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Expense report approved successfully."
            }
        except Exception as e:
            return handle_api_exception(e)

    @http.route(f"{API_PREFIX}/hr/expense/refuse", type="json", auth="user", methods=["POST"])
    def expense_refuse(self, **payload):
        """Refuse/Reject an expense sheet."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            sheet_id = payload.get("sheet_id")
            expense_id = payload.get("expense_id")
            reason = payload.get("reason")
            
            if not reason:
                raise ValidationError("reason is required.")
            if not sheet_id and not expense_id:
                raise ValidationError("sheet_id or expense_id is required.")
                
            if sheet_id:
                sheet = api_env["hr.expense.sheet"].sudo().browse(int(sheet_id))
            else:
                expense = api_env["hr.expense"].sudo().browse(int(expense_id))
                if not expense.exists():
                    raise ValidationError("Expense record not found.")
                sheet = expense.sheet_id

            if not sheet or not sheet.exists():
                raise ValidationError("Expense report not found.")
                
            # Perform refusal: run security policy check first with API context, then execute action with sudo
            sheet.with_context(mobile_api_user_id=api_env.context.get('mobile_api_user_id'))._check_app_workflow_policy('refuse')
            sheet.sudo()._do_refuse(reason)
            
            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Expense report refused successfully."
            }
        except Exception as e:
            return handle_api_exception(e)

    @http.route(f"{API_PREFIX}/hr/expense/drafts", type="json", auth="user", methods=["POST"])
    def expense_drafts(self, **payload):
        """Fetch draft/unsubmitted expenses for the employee."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            employee_id = payload.get("employee_id")
            
            if not employee_id:
                raise ValidationError("employee_id is required.")
                
            employee = api_env["hr.employee"].sudo().browse(int(employee_id))
            if not employee.exists():
                raise ValidationError("Employee not found.")

            expenses = api_env["hr.expense"].sudo().search([
                ("employee_id", "=", employee.id),
                ("sheet_id", "=", False),
                ("state", "=", "draft")
            ], order="date desc, id desc")

            data = []
            for rec in expenses:
                data.append({
                    "id": rec.id,
                    "title": rec.name or "",
                    "category": rec.product_id.name or "",
                    "category_id": rec.product_id.id if rec.product_id else None,
                    "amount": float(rec.total_amount_currency or rec.total_amount or 0.0),
                    "date": rec.date.strftime("%Y-%m-%d") if rec.date else "",
                    "description": rec.description or "",
                })

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Draft expenses fetched successfully.",
                "data": data
            }
        except Exception as e:
            return handle_api_exception(e)

    @http.route(f"{API_PREFIX}/hr/expense/sheet/create", type="json", auth="user", methods=["POST"])
    def expense_sheet_create(self, **payload):
        """Create an expense sheet, link/update/create expenses, and submit it."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            employee_id = payload.get("employee_id")
            title = payload.get("title")
            description = payload.get("description", "")
            expenses_data = payload.get("expenses", [])

            if not employee_id:
                raise ValidationError("employee_id is required.")

            employee = api_env["hr.employee"].sudo().browse(int(employee_id))
            if not employee.exists():
                raise ValidationError("Employee not found.")

            # Create the sheet
            sheet_title = title or f"Expense Report - {fields.Date.context_today(employee)}"
            sheet = api_env["hr.expense.sheet"].sudo().create({
                "name": sheet_title,
                "employee_id": employee.id,
                "request_source": "app",
                "description": description,
            })

            # Process expenses
            for item in expenses_data:
                if item.get("id"):
                    # Existing expense (to be updated and linked)
                    expense = api_env["hr.expense"].sudo().browse(int(item["id"]))
                    if not expense.exists() or expense.employee_id != employee or expense.sheet_id:
                        raise ValidationError(f"Invalid or already submitted expense ID: {item['id']}")
                    
                    update_vals = {}
                    if item.get("category_id"):
                        update_vals["product_id"] = int(item["category_id"])
                    if item.get("amount"):
                        update_vals["total_amount_currency"] = float(item["amount"])
                    if item.get("date"):
                        update_vals["date"] = fields.Date.from_string(item["date"])
                    if "description" in item:
                        update_vals["description"] = item["description"]
                    if item.get("title"):
                        update_vals["name"] = item["title"]
                        
                    if update_vals:
                        expense.write(update_vals)
                        
                    expense.write({"sheet_id": sheet.id})
                else:
                    # New expense (to be created and linked)
                    category_id = item.get("category_id")
                    if not category_id:
                        raise ValidationError("category_id is required for new expenses.")
                    category = api_env["product.product"].sudo().browse(int(category_id))
                    if not category.exists() or not category.can_be_expensed:
                        raise ValidationError(f"Invalid category ID: {category_id}")
                        
                    expense_vals = {
                        "employee_id": employee.id,
                        "product_id": category.id,
                        "name": item.get("title") or category.name,
                        "total_amount_currency": float(item.get("amount", 0.0)),
                        "date": fields.Date.from_string(item.get("date")) if item.get("date") else fields.Date.context_today(employee),
                        "payment_mode": item.get("payment_mode", "own_account"),
                        "description": item.get("description", ""),
                        "sheet_id": sheet.id,
                    }
                    api_env["hr.expense"].sudo().create(expense_vals)

            # Submit the sheet
            sheet.action_submit_sheet()

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Expense report created and submitted successfully.",
                "data": {
                    "id": sheet.id,
                    "title": sheet.name,
                    "state": sheet.state,
                    "total_amount": float(sheet.total_amount or 0.0),
                }
            }
        except Exception as e:
            return handle_api_exception(e)

    @http.route(f"{API_PREFIX}/hr/expense/sheet/list", type="json", auth="user", methods=["POST"])
    def expense_sheet_list(self, **payload):
        """Fetch own or pending approval expense sheets/reports."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            employee_id = payload.get("employee_id")
            mode = payload.get("mode", "own") # 'own' or 'pending'
            state = payload.get("state") # optional: 'draft', 'submit', 'approve', 'done', 'cancel'
            start_date_str = payload.get("start_date") # optional YYYY-MM-DD
            end_date_str = payload.get("end_date") # optional YYYY-MM-DD

            if not employee_id:
                raise ValidationError("employee_id is required.")
                
            employee = api_env["hr.employee"].sudo().browse(int(employee_id))
            if not employee.exists():
                raise ValidationError("Employee not found.")

            domain = []
            if mode == "pending":
                domain.append(("employee_id.parent_id", "=", employee.id))
                if state:
                    if state == "approve":
                        domain.append(("state", "in", ["approve", "post", "done"]))
                    else:
                        domain.append(("state", "=", state))
                else:
                    domain.append(("state", "in", ["submit", "approve", "post", "done", "cancel"]))
            else:
                domain.append(("employee_id", "=", employee.id))
                if state:
                    if state == "approve":
                        domain.append(("state", "in", ["approve", "post", "done"]))
                    else:
                        domain.append(("state", "=", state))

            if start_date_str:
                domain.append(("create_date", ">=", fields.Datetime.to_datetime(f"{start_date_str} 00:00:00")))
            if end_date_str:
                domain.append(("create_date", "<=", fields.Datetime.to_datetime(f"{end_date_str} 23:59:59")))

            sheets = api_env["hr.expense.sheet"].sudo().search(domain, order="create_date desc, id desc")
            
            # Resolve current employee/user for manager check
            mobile_api_user_id = api_env.context.get('mobile_api_user_id')
            current_employee = False
            if mobile_api_user_id:
                mobile_user = api_env['res.mobile.user'].sudo().browse(mobile_api_user_id)
                current_employee = mobile_user.employee_id
            else:
                current_employee = api_env.user.employee_id

            data = []
            status_labels = {
                "draft": "DRAFT",
                "submit": "TO APPROVE",
                "approve": "APPROVED",
                "post": "POSTED",
                "done": "PAID",
                "cancel": "REFUSED"
            }

            for rec in sheets:
                # Custom approval logic: only direct manager or administrator can approve
                user_can_approve = (rec.state == 'submit') and (api_env.is_admin() or (current_employee and rec.employee_id.parent_id == current_employee))

                data.append({
                    "id": rec.id,
                    "title": rec.name or "",
                    "date": rec.create_date.strftime("%Y-%m-%d") if rec.create_date else "",
                    "amount": float(rec.total_amount or 0.0),
                    "status": rec.state or "draft",
                    "status_label": status_labels.get(rec.state, "DRAFT"),
                    "description": rec.description or "",
                    "can_approve": user_can_approve,
                    "employee_name": rec.employee_id.name or "",
                })

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": f"Expense sheets ({mode}) fetched successfully.",
                "data": data
            }
        except Exception as e:
            return handle_api_exception(e)

    @http.route(f"{API_PREFIX}/hr/expense/sheet/details", type="json", auth="user", methods=["POST"])
    def expense_sheet_details(self, **payload):
        """Fetch details and line items of a specific expense sheet."""
        try:
            _, api_env, payload = get_mobile_api_context(payload)
            sheet_id = payload.get("sheet_id")
            
            if not sheet_id:
                raise ValidationError("sheet_id is required.")
                
            sheet = api_env["hr.expense.sheet"].sudo().browse(int(sheet_id))
            if not sheet.exists():
                raise ValidationError("Expense sheet not found.")

            status_labels = {
                "draft": "DRAFT",
                "submit": "TO APPROVE",
                "approve": "APPROVED",
                "post": "POSTED",
                "done": "PAID",
                "cancel": "REFUSED"
            }

            lines = []
            for line in sheet.expense_line_ids:
                lines.append({
                    "id": line.id,
                    "title": line.name or "",
                    "category": line.product_id.name or "",
                    "category_id": line.product_id.id if line.product_id else None,
                    "amount": float(line.total_amount_currency or line.total_amount or 0.0),
                    "date": line.date.strftime("%Y-%m-%d") if line.date else "",
                    "description": line.description or "",
                })

            # Custom approval logic for mobile app source sheets
            mobile_api_user_id = api_env.context.get('mobile_api_user_id')
            current_employee = False
            if mobile_api_user_id:
                mobile_user = api_env['res.mobile.user'].sudo().browse(mobile_api_user_id)
                current_employee = mobile_user.employee_id
            else:
                current_employee = api_env.user.employee_id

            # Custom approval logic: only direct manager or administrator can approve
            if api_env.is_admin():
                user_can_approve = (sheet.state == 'submit')
            elif mobile_api_user_id:
                user_can_approve = (sheet.state == 'submit') and current_employee and (sheet.employee_id.parent_id == current_employee)
            else:
                user_can_approve = (sheet.state == 'submit') and (sheet.employee_id.parent_id.user_id == api_env.user or current_employee and sheet.employee_id.parent_id == current_employee)

            data = {
                "id": sheet.id,
                "title": sheet.name or "",
                "employee_id": sheet.employee_id.id,
                "employee_name": sheet.employee_id.name or "",
                "date": sheet.create_date.strftime("%Y-%m-%d") if sheet.create_date else "",
                "amount": float(sheet.total_amount or 0.0),
                "status": sheet.state or "draft",
                "status_label": status_labels.get(sheet.state, "DRAFT"),
                "description": sheet.description or "",
                "can_approve": user_can_approve,
                "expenses": lines,
            }

            return {
                "success": True,
                "api_version": API_VERSION,
                "message": "Expense sheet details fetched successfully.",
                "data": data
            }
        except Exception as e:
            return handle_api_exception(e)

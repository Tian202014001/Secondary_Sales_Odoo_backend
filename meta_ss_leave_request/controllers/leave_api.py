import base64
import json
from odoo import http, fields
from odoo.exceptions import ValidationError, UserError, AccessError
from odoo.http import request
from odoo.addons.meta_ss_rest_api.utils.common import (
    API_PREFIX,
    API_VERSION,
    error_response,
    get_mobile_api_context,
    mobile_api_error_boundary,
    handle_api_exception,
    require_ui_access,
)


from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey


class LeaveAPI(http.Controller):

    @http.route(f"{API_PREFIX}/hr/leave/types", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def get_leave_types(self, **payload):
        """Fetch leave types with allocation balances"""
        mobile_user, api_env, payload = get_mobile_api_context(payload)
        require_ui_access(mobile_user, AccessKey.HR_LEAVE)
        employee_id = payload.get("employee_id")

        if not employee_id:
            return error_response(400, "employee_id is required")

        employee = api_env['hr.employee'].sudo().browse(int(employee_id))
        if not employee.exists():
            return error_response(404, "Employee not found")

        lang = api_env.user.sudo().lang or 'en_US'

        query = """
            SELECT
                hls.id as leave_type_id,
                COALESCE(
                    hls.name->>%s,
                    hls.name->>'en_US',
                    hls.name::text
                ) as leave_type_name,
                hls.requires_allocation,
                COALESCE(SUM(hla.number_of_days), 0) as total_allocated,
                COALESCE(
                    (SELECT SUM(hl.number_of_days)
                     FROM hr_leave hl
                     WHERE hl.holiday_status_id = hls.id
                     AND hl.employee_id = %s
                     AND hl.state IN ('confirm', 'validate1', 'validate')), 0
                ) as total_taken,
                COALESCE(SUM(hla.number_of_days), 0) - COALESCE(
                    (SELECT SUM(hl.number_of_days)
                     FROM hr_leave hl
                     WHERE hl.holiday_status_id = hls.id
                     AND hl.employee_id = %s
                     AND hl.state IN ('confirm', 'validate1', 'validate')), 0
                ) as remaining_leaves
            FROM
                hr_leave_type hls
            LEFT JOIN
                hr_leave_allocation hla ON hla.holiday_status_id = hls.id
                AND hla.employee_id = %s
                AND hla.state = 'validate'
            WHERE
                hls.active = true
            GROUP BY
                hls.id, hls.name, hls.requires_allocation
            HAVING
                (COALESCE(SUM(hla.number_of_days), 0) > 0 OR hls.requires_allocation = 'no')
            ORDER BY
                hls.name
        """

        request.env.cr.execute(query, (lang, employee.id, employee.id, employee.id))
        results = request.env.cr.dictfetchall()

        data = []
        for row in results:
            total_allocated = float(row['total_allocated'])
            total_taken = float(row['total_taken'])
            remaining_leaves = float(row['remaining_leaves'])
            requires_allocation = row['requires_allocation']

            data.append({
                "id": row['leave_type_id'],
                "name": row['leave_type_name'],
                "requires_allocation": requires_allocation,
                "total_allocated": total_allocated,
                "total_used": total_taken,
                "remaining": remaining_leaves,
                "is_available": remaining_leaves > 0 if requires_allocation == 'yes' else True
            })

        return {"success": True, "data": data}


    @http.route(f"{API_PREFIX}/hr/leave/request", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def submit_leave_request(self, **payload):
        """Submit a new leave request with optional attachment"""
        mobile_user, api_env, payload = get_mobile_api_context(payload)
        require_ui_access(mobile_user, AccessKey.HR_LEAVE_CREATE)

        employee_id = payload.get("employee_id")
        leave_type_id = payload.get("leave_type_id")
        date_from = payload.get("date_from")
        date_to = payload.get("date_to")
        reason = payload.get("reason", "")
        attachment_b64 = payload.get("attachment")
        attachment_name = payload.get("attachment_name")

        if not all([employee_id, leave_type_id, date_from, date_to]):
            return error_response(400, "employee_id, leave_type_id, date_from, and date_to are required")

        leave_vals = {
            'employee_id': int(employee_id),
            'holiday_status_id': int(leave_type_id),
            'request_date_from': fields.Date.to_date(date_from),
            'request_date_to': fields.Date.to_date(date_to),
            'date_from': fields.Datetime.to_datetime(f"{date_from} 00:00:00"),
            'date_to': fields.Datetime.to_datetime(f"{date_to} 23:59:59"),
            'name': reason,
            'request_source': 'app',
        }

        # Create the leave record (sudo: the integration user is locked down,
        # and creating a leave triggers manager/user computes that read res.users)
        leave = api_env['hr.leave'].sudo().create(leave_vals)

        # Process attachment if present
        if attachment_b64:
            filename = attachment_name or f"Leave_Attachment_{leave.id}.pdf"
            attachment = api_env['ir.attachment'].sudo().create({
                'name': filename,
                'type': 'binary',
                'datas': attachment_b64,
                'res_model': 'hr.leave',
                'res_id': leave.id,
            })
            # Post to chatter log note so it links to the message log
            leave.message_post(
                body=f"Attachment '{filename}' uploaded from Mobile App.",
                attachment_ids=[attachment.id]
            )

        # Trigger duration computation (number of days)
        leave._compute_duration()


        return {
            "success": True,
            "message": "Leave request submitted successfully",
            "data": {
                "leave_id": leave.id,
                "reference": f"#{leave.id}",
                "status": leave.state
            }
        }


    @http.route(f"{API_PREFIX}/hr/leave/list", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def list_leaves(self, **payload):
        """Unified endpoint for listing leaves (Own, Pending, Approved, Rejected, All)"""
        mobile_user, api_env, payload = get_mobile_api_context(payload)
        require_ui_access(mobile_user, AccessKey.HR_LEAVE)

        employee_id = payload.get("employee_id")
        tab_filter = payload.get("tab_filter", "own") # own, pending, approved, rejected, all
        date_from = payload.get("date_from")
        date_to = payload.get("date_to")
        search_query = payload.get("search_query")

        if not employee_id:
            return error_response(400, "employee_id is required")

        current_employee = api_env['hr.employee'].sudo().browse(int(employee_id))

        domain = []

        if tab_filter == "own":
            domain.append(('employee_id', '=', current_employee.id))
        else:
            # Manager view: look for leaves of subordinates
            domain.append(('employee_id.parent_id', '=', current_employee.id))

            if tab_filter == "pending":
                domain.append(('state', 'in', ['confirm', 'validate1']))
            elif tab_filter == "approved":
                domain.append(('state', '=', 'validate'))
            elif tab_filter == "rejected":
                domain.append(('state', '=', 'refuse'))

        if date_from:
            domain.append(('request_date_from', '>=', fields.Date.to_date(date_from)))
        if date_to:
            domain.append(('request_date_to', '<=', fields.Date.to_date(date_to)))

        if search_query:
            domain.append('|', ('employee_id.name', 'ilike', search_query), ('id', 'ilike', search_query))

        leaves = api_env['hr.leave'].sudo().search(domain, order="id desc")

        data = []
        for leave in leaves:
            attachments = api_env['ir.attachment'].sudo().search([
                ('res_model', '=', 'hr.leave'),
                ('res_id', '=', leave.id)
            ])

            data.append({
                "leave_id": leave.id,
                "reference_id": f"#{leave.id}",
                "employee_name": leave.employee_id.name,
                "department": leave.employee_id.department_id.name or "",
                "leave_type": leave.holiday_status_id.name,
                "date_from": str(leave.request_date_from),
                "date_to": str(leave.request_date_to),
                "duration": f"{leave.number_of_days} days",
                "applied_on": str(leave.create_date.date()),
                "status": leave.state, # draft, confirm, validate, refuse
                "pending_approver": leave.employee_id.parent_id.name if leave.state in ['confirm', 'validate1'] else "",
                "reason": leave.name or "",
                "has_attachment": bool(attachments),
                "is_my_request": leave.employee_id.id == current_employee.id,
                "can_approve": leave.employee_id.parent_id.id == current_employee.id and leave.state in ['confirm', 'validate1'],
            })

        return {"success": True, "data": data}


    @http.route(f"{API_PREFIX}/hr/leave/action", type="json", auth="user", methods=["POST"])
    @mobile_api_error_boundary
    def action_leave(self, **payload):
        """Approve or Reject a leave (For Managers)"""
        _, api_env, payload = get_mobile_api_context(payload)

        employee_id = payload.get("employee_id")
        leave_id = payload.get("leave_id")
        action = payload.get("action") # 'approve' or 'reject'

        if not all([employee_id, leave_id, action]):
            return error_response(400, "employee_id, leave_id, and action are required")

        leave = api_env['hr.leave'].sudo().browse(int(leave_id))
        if not leave.exists():
            return error_response(404, "Leave request not found")

        # Verify the current user is the manager
        current_employee = api_env['hr.employee'].sudo().browse(int(employee_id))
        if leave.employee_id.parent_id != current_employee:
            return error_response(403, "You are not authorized to approve/reject this leave")

        if action == 'approve':
            leave.action_approve()
        elif action == 'reject':
            leave.action_refuse()
        else:
            return error_response(400, "Invalid action. Use 'approve' or 'reject'")

        return {
            "success": True,
            "message": f"Leave {action}d successfully",
            "new_status": leave.state
        }



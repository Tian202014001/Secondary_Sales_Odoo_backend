# -*- coding: utf-8 -*-

import ast
from pathlib import Path

from odoo.exceptions import AccessDenied, ValidationError
from odoo.tests.common import TransactionCase, tagged

from odoo.addons.meta_ss_rest_api.utils.access_keys import AccessKey
from odoo.addons.meta_ss_rest_api.utils.common import (
    contact_type_key,
    require_any_ui_access,
    require_contact_type_access,
    require_sale_type_access,
    require_ui_access,
    sale_type_key,
)


ADDONS_ROOT = Path(__file__).resolve().parents[2]
GATE_HELPERS = {
    "require_ui_access",
    "require_any_ui_access",
    "require_sale_type_access",
    "require_contact_type_access",
}


PROTECTED_ENDPOINT_MATRIX = {
    "meta_ss_sales/controllers/sales.py": {
        "get_sale_orders": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_ORDERS_LIST", "SECONDARY_ORDERS_LIST"},
        },
        "get_mediums": {
            "helper": "require_any_ui_access",
            "keys": {"PRIMARY_ORDERS_CREATE", "SECONDARY_ORDERS_CREATE"},
        },
        "create_sale_order": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_ORDERS_CREATE", "SECONDARY_ORDERS_CREATE"},
        },
        "update_sale_order": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_ORDERS_CREATE", "SECONDARY_ORDERS_CREATE"},
        },
    },
    "meta_ss_sales/controllers/sale_order_details.py": {
        "get_sale_order_detail": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_ORDERS_DETAIL", "SECONDARY_ORDERS_LIST"},
        },
        "sale_order_action": {
            "helper": "require_sale_type_access",
            "keys": {
                "PRIMARY_ORDERS_CONFIRM",
                "SECONDARY_ORDERS_CONFIRM",
                "PRIMARY_ORDERS_CANCEL",
                "SECONDARY_ORDERS_CANCEL",
                "PRIMARY_ORDERS_CREATE",
                "SECONDARY_ORDERS_CREATE",
            },
        },
        "print_sale_order": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_ORDERS_DETAIL", "SECONDARY_ORDERS_LIST"},
        },
    },
    "meta_ss_sales/controllers/deliveries.py": {
        "get_deliveries": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_DELIVERIES_LIST", "SECONDARY_DELIVERIES_LIST"},
        },
        "prepare_delivery": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_DELIVERIES_VALIDATE", "SECONDARY_DELIVERIES_VALIDATE"},
        },
        "get_delivery_product_lots": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_DELIVERIES_VALIDATE", "SECONDARY_DELIVERIES_VALIDATE"},
        },
        "get_delivery_auto_assign_lots": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_DELIVERIES_VALIDATE", "SECONDARY_DELIVERIES_VALIDATE"},
        },
        "delivery_action": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_DELIVERIES_VALIDATE", "SECONDARY_DELIVERIES_VALIDATE"},
        },
    },
    "meta_ss_transfer/controllers/returns.py": {
        "prepare_return": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_RETURNS_CREATE", "SECONDARY_RETURNS_CREATE"},
        },
        "get_returns": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_RETURNS_LIST", "SECONDARY_RETURNS_LIST"},
        },
        "get_return_products": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_RETURNS_CREATE", "SECONDARY_RETURNS_CREATE"},
        },
        "get_return_product_lots": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_RETURNS_CREATE", "SECONDARY_RETURNS_CREATE"},
        },
        "create_return": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_RETURNS_CREATE", "SECONDARY_RETURNS_CREATE"},
        },
        "get_return_details": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_RETURNS_LIST", "SECONDARY_RETURNS_LIST"},
        },
        "update_return": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_RETURNS_SAVE", "SECONDARY_RETURNS_SAVE"},
        },
        "return_action": {
            "helper": "require_sale_type_access",
            "keys": {
                "PRIMARY_RETURNS_VALIDATE",
                "SECONDARY_RETURNS_VALIDATE",
                "PRIMARY_RETURNS_CANCEL",
                "SECONDARY_RETURNS_CANCEL",
                "PRIMARY_RETURNS_SAVE",
                "SECONDARY_RETURNS_SAVE",
            },
        },
    },
    "meta_ss_transfer/controllers/scraps.py": {
        "prepare_scrap": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_SCRAPS_CREATE", "SECONDARY_SCRAPS_CREATE"},
        },
        "get_scraps": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_SCRAPS_LIST", "SECONDARY_SCRAPS_LIST"},
        },
        "get_scrap_products": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_SCRAPS_CREATE", "SECONDARY_SCRAPS_CREATE"},
        },
        "get_scrap_product_lots": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_SCRAPS_CREATE", "SECONDARY_SCRAPS_CREATE"},
        },
        "create_scrap": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_SCRAPS_CREATE", "SECONDARY_SCRAPS_CREATE"},
        },
        "get_scrap_details": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_SCRAPS_LIST", "SECONDARY_SCRAPS_LIST"},
        },
        "update_scrap": {
            "helper": "require_sale_type_access",
            "keys": {"PRIMARY_SCRAPS_SAVE", "SECONDARY_SCRAPS_SAVE"},
        },
        "scrap_action": {
            "helper": "require_sale_type_access",
            "keys": {
                "PRIMARY_SCRAPS_VALIDATE",
                "SECONDARY_SCRAPS_VALIDATE",
                "PRIMARY_SCRAPS_CANCEL",
                "SECONDARY_SCRAPS_CANCEL",
                "PRIMARY_SCRAPS_SAVE",
                "SECONDARY_SCRAPS_SAVE",
            },
        },
    },
    "meta_ss_transfer/controllers/virtual_transfers.py": {
        "prepare_virtual_transfer": {
            "helper": "require_ui_access",
            "keys": {"SECONDARY_TRANSFERS_CREATE"},
        },
        "get_virtual_transfer_products": {
            "helper": "require_ui_access",
            "keys": {"SECONDARY_TRANSFERS_CREATE"},
        },
        "get_virtual_transfer_product_lots": {
            "helper": "require_ui_access",
            "keys": {"SECONDARY_TRANSFERS_CREATE"},
        },
        "get_virtual_transfer_auto_assign_lots": {
            "helper": "require_ui_access",
            "keys": {"SECONDARY_TRANSFERS_CREATE"},
        },
        "create_van_loading_transfer": {
            "helper": "require_ui_access",
            "keys": {"SECONDARY_TRANSFERS_CREATE"},
        },
        "get_virtual_transfers": {
            "helper": "require_ui_access",
            "keys": {"SECONDARY_TRANSFERS_LIST"},
        },
        "get_virtual_transfer_detail": {
            "helper": "require_ui_access",
            "keys": {"SECONDARY_TRANSFERS_DETAIL"},
        },
        "update_virtual_transfer": {
            "helper": "require_ui_access",
            "keys": {"SECONDARY_TRANSFERS_CREATE"},
        },
        "virtual_transfer_action": {
            "helper": "require_ui_access",
            "keys": {
                "SECONDARY_TRANSFERS_VALIDATE",
                "SECONDARY_TRANSFERS_CANCEL",
                "SECONDARY_TRANSFERS_CREATE",
            },
        },
    },
    "meta_ss_contact/controllers/contacts.py": {
        "get_contacts": {
            "helpers": {"require_contact_type_access", "require_any_ui_access"},
            "keys": {"PRIMARY_DISTRIBUTORS_LIST", "SECONDARY_OUTLETS_LIST"},
        },
        "create_contact": {
            "helper": "require_contact_type_access",
            "keys": {"PRIMARY_DISTRIBUTORS_CREATE", "SECONDARY_OUTLETS_CREATE"},
        },
        "get_contact": {
            "helpers": {"require_contact_type_access", "require_any_ui_access"},
            "keys": {"PRIMARY_DISTRIBUTORS_DETAIL", "SECONDARY_OUTLETS_LIST"},
        },
        "update_contact": {
            "helper": "require_contact_type_access",
            "keys": {"PRIMARY_DISTRIBUTORS_CREATE", "SECONDARY_OUTLETS_EDIT"},
        },
        "get_contact_visit_history": {
            "helpers": {"require_contact_type_access", "require_any_ui_access"},
            "keys": {"PRIMARY_DISTRIBUTORS_DETAIL", "SECONDARY_OUTLETS_LIST"},
        },
    },
    "meta_ss_route_management/controllers/routes.py": {
        "get_employee_routes": {"helper": "require_ui_access", "keys": {"SECONDARY_ROUTES_LIST"}},
        "create_employee_route": {"helper": "require_ui_access", "keys": {"SECONDARY_ROUTES_CREATE"}},
        "add_employee_route_outlet": {"helper": "require_ui_access", "keys": {"SECONDARY_ROUTES_ADD_OUTLET"}},
        "get_employee_route_detail": {"helper": "require_ui_access", "keys": {"SECONDARY_ROUTES_DETAIL"}},
        "update_employee_route": {"helper": "require_ui_access", "keys": {"SECONDARY_ROUTES_CREATE"}},
        "remove_employee_route_outlet": {"helper": "require_ui_access", "keys": {"SECONDARY_ROUTES_ADD_OUTLET"}},
        "get_employee_visits": {"helper": "require_ui_access", "keys": {"SECONDARY_VISITS_LIST"}},
        "create_visit": {"helper": "require_ui_access", "keys": {"SECONDARY_VISITS_CHECK_IN"}},
        "update_visit": {"helper": "require_ui_access", "keys": {"SECONDARY_VISITS_CHECK_OUT"}},
        "get_today_visits": {"helper": "require_ui_access", "keys": {"SECONDARY_VISITS_LIST"}},
    },
    "meta_ss_rest_api/controllers/van_loading.py": {
        "get_van_loading_targets": {"helper": "require_ui_access", "keys": {"SECONDARY_VAN_LOADING_LIST"}},
    },
    "meta_ss_employee/controllers/employees.py": {
        "get_employees": {"helper": "require_ui_access", "keys": {"DASHBOARD_SALES_OFFICERS_LIST"}},
        "create_employee": {"helper": "require_ui_access", "keys": {"DASHBOARD_SALES_OFFICERS_CREATE"}},
        "get_employee": {"helper": "require_ui_access", "keys": {"DASHBOARD_SALES_OFFICERS_DETAIL"}},
        "update_employee": {"helper": "require_ui_access", "keys": {"DASHBOARD_SALES_OFFICERS_CREATE"}},
    },
    "meta_ss_attendance/controllers/attendance.py": {
        "attendance_status": {"helper": "require_ui_access", "keys": {"HR_ATTENDANCE"}},
        "attendance_history": {"helper": "require_ui_access", "keys": {"HR_ATTENDANCE"}},
        "attendance_action": {"helper": "require_ui_access", "keys": {"HR_ATTENDANCE"}},
    },
    "meta_ss_location_tracking/controllers/location_api.py": {
        "get_my_team": {"helper": "require_ui_access", "keys": {"DASHBOARD_MODULE"}},
        "get_employee_checkpoints": {"helper": "require_ui_access", "keys": {"DASHBOARD_MODULE"}},
    },
    "meta_ss_expense/controllers/expense.py": {
        "expense_categories": {"helper": "require_ui_access", "keys": {"ACCOUNTS_EXPENSE"}},
        "expense_list": {"helper": "require_ui_access", "keys": {"ACCOUNTS_EXPENSE"}},
        "expense_drafts": {"helper": "require_ui_access", "keys": {"ACCOUNTS_EXPENSE"}},
        "expense_sheet_create": {"helper": "require_ui_access", "keys": {"ACCOUNTS_EXPENSE_CREATE"}},
        "expense_sheet_list": {"helper": "require_ui_access", "keys": {"ACCOUNTS_EXPENSE"}},
        "expense_sheet_details": {"helper": "require_ui_access", "keys": {"ACCOUNTS_EXPENSE"}},
    },
    "meta_ss_leave_request/controllers/leave_api.py": {
        "get_leave_types": {"helper": "require_ui_access", "keys": {"HR_LEAVE"}},
        "submit_leave_request": {"helper": "require_ui_access", "keys": {"HR_LEAVE_CREATE"}},
        "list_leaves": {"helper": "require_ui_access", "keys": {"HR_LEAVE"}},
    },
}

INTENTIONALLY_UNGATED_MATRIX = {
    "meta_ss_location_tracking/controllers/location_api.py": {"sync_employee_locations"},
    "meta_ss_expense/controllers/expense.py": {"expense_approve", "expense_refuse"},
    "meta_ss_leave_request/controllers/leave_api.py": {"action_leave"},
    "meta_ss_rest_api/controllers/products.py": {"get_products"},
    "meta_ss_rest_api/controllers/locations.py": {"get_locations"},
    "meta_ss_rest_api/controllers/warehouses.py": {"get_warehouses", "get_product_available_lots"},
    "meta_ss_rest_api/controllers/access_control.py": {"get_permissions", "sync_catalog"},
    "meta_firebase_push_notification/controllers/device.py": {"register_device", "unregister_device"},
    "meta_api_user/controllers/mobile_auth_controller.py": {"bootstrap_session", "login", "refresh", "logout"},
}

NEEDS_REVIEW_MATRIX = {
    "meta_ss_transfer/controllers/virtual_locations.py": {
        "get_virtual_locations",
        "create_virtual_location",
        "get_virtual_location_detail",
    },
}


class EndpointSourceAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.functions = {}

    def visit_FunctionDef(self, node):
        self.functions[node.name] = {
            "helpers": set(),
            "access_keys": set(),
            "route_count": sum(
                1
                for decorator in node.decorator_list
                if self._decorator_name(decorator) == "http.route"
            ),
        }
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = self._call_name(child.func)
                if name in GATE_HELPERS:
                    self.functions[node.name]["helpers"].add(name)
            if isinstance(child, ast.Attribute) and self._call_name(child.value) == "AccessKey":
                self.functions[node.name]["access_keys"].add(child.attr)
        self.generic_visit(node)

    def _decorator_name(self, node):
        if isinstance(node, ast.Call):
            return self._call_name(node.func)
        return self._call_name(node)

    def _call_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return ""


def analyze_controller(relative_path):
    tree = ast.parse((ADDONS_ROOT / relative_path).read_text())
    analyzer = EndpointSourceAnalyzer()
    analyzer.visit(tree)
    return analyzer.functions


def access_key_values():
    return {
        name: value
        for name, value in vars(AccessKey).items()
        if name.isupper() and isinstance(value, str)
    }


@tagged("post_install", "-at_install")
class TestEndpointOperationAccessMatrix(TransactionCase):
    def test_every_expected_operation_endpoint_has_its_gate(self):
        for relative_path, expected_functions in PROTECTED_ENDPOINT_MATRIX.items():
            functions = analyze_controller(relative_path)
            for function_name, expected in expected_functions.items():
                with self.subTest(file=relative_path, function=function_name):
                    self.assertIn(function_name, functions)
                    self.assertGreater(functions[function_name]["route_count"], 0)
                    expected_helpers = expected.get("helpers") or {expected["helper"]}
                    self.assertTrue(
                        expected_helpers.issubset(functions[function_name]["helpers"]),
                        "%s.%s is missing helper(s) %s; found %s"
                        % (
                            relative_path,
                            function_name,
                            sorted(expected_helpers),
                            sorted(functions[function_name]["helpers"]),
                        ),
                    )
                    self.assertTrue(
                        expected["keys"].issubset(functions[function_name]["access_keys"]),
                        "%s.%s is missing key(s) %s; found %s"
                        % (
                            relative_path,
                            function_name,
                            sorted(expected["keys"]),
                            sorted(functions[function_name]["access_keys"]),
                        ),
                    )

    def test_intentionally_ungated_endpoints_have_no_ui_resource_gate(self):
        for relative_path, function_names in INTENTIONALLY_UNGATED_MATRIX.items():
            functions = analyze_controller(relative_path)
            for function_name in function_names:
                with self.subTest(file=relative_path, function=function_name):
                    self.assertIn(function_name, functions)
                    self.assertTrue(
                        functions[function_name]["helpers"].isdisjoint(GATE_HELPERS),
                        "%s.%s should stay outside UI-resource operation gating; found %s"
                        % (relative_path, function_name, sorted(functions[function_name]["helpers"])),
                    )

    def test_setup_endpoints_that_need_review_are_still_ungated_and_visible_in_tests(self):
        for relative_path, function_names in NEEDS_REVIEW_MATRIX.items():
            functions = analyze_controller(relative_path)
            for function_name in function_names:
                with self.subTest(file=relative_path, function=function_name):
                    self.assertIn(function_name, functions)
                    self.assertTrue(
                        functions[function_name]["helpers"].isdisjoint(GATE_HELPERS),
                        "%s.%s changed gate status; update the access-control decision and matrix."
                        % (relative_path, function_name),
                    )

    def test_every_access_key_constant_exists_in_active_database_catalog(self):
        constants = access_key_values()
        active_keys = set(
            self.env["mobile.ui.resource"]
            .sudo()
            .search([("active", "=", True), ("key", "in", list(constants.values()))])
            .mapped("key")
        )
        missing = sorted(set(constants.values()) - active_keys)
        self.assertFalse(missing, "AccessKey constants missing from active catalog: %s" % missing)


@tagged("post_install", "-at_install")
class TestUiAccessHelpers(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Resource = cls.env["mobile.ui.resource"].sudo()
        cls.Module = cls.env["ss.module"].sudo()
        cls.Group = cls.env["res.mobile.user.group"].sudo()
        cls.Employee = cls.env["hr.employee"].sudo()
        cls.MobileUser = cls.env["res.mobile.user"].sudo()

        cls.module = cls.Module.create({"name": "Test Access Module", "code": "TST_ACCESS"})
        cls.granted_screen = cls.Resource.create({
            "key": "test.access.screen",
            "res_type": "screen",
            "module": "test",
            "label": "Test Screen",
            "module_ids": [(6, 0, cls.module.ids)],
            "active": True,
        })
        cls.granted_action = cls.Resource.create({
            "key": "test.access.action",
            "res_type": "action",
            "module": "test",
            "label": "Test Action",
            "module_ids": [(6, 0, cls.module.ids)],
            "active": True,
        })
        cls.hidden_action = cls.Resource.create({
            "key": "test.hidden.action",
            "res_type": "action",
            "module": "test",
            "label": "Hidden Action",
            "module_ids": [(6, 0, cls.module.ids)],
            "active": True,
        })
        cls.inactive_resource = cls.Resource.create({
            "key": "test.inactive.action",
            "res_type": "action",
            "module": "test",
            "label": "Inactive Action",
            "module_ids": [(6, 0, cls.module.ids)],
            "active": False,
        })
        cls.unmapped_resource = cls.Resource.create({
            "key": "test.unmapped.action",
            "res_type": "action",
            "module": "test",
            "label": "Unmapped Action",
            "active": True,
        })
        cls.group = cls.Group.create({
            "name": "Test Access Group",
            "code": "TST_ACCESS_GROUP",
            "module_ids": [(6, 0, cls.module.ids)],
            "hidden_button_ids": [(6, 0, cls.hidden_action.ids)],
        })
        cls.empty_group = cls.Group.create({
            "name": "Test Empty Access Group",
            "code": "TST_EMPTY_ACCESS_GROUP",
        })
        cls.employee = cls.Employee.create({
            "name": "Test Access Employee",
            "mobile_user_group_id": cls.group.id,
        })
        cls.empty_employee = cls.Employee.create({
            "name": "Test Empty Access Employee",
            "mobile_user_group_id": cls.empty_group.id,
        })
        cls.no_group_employee = cls.Employee.create({"name": "Test No Group Employee"})
        cls.mobile_user = cls.MobileUser.create({
            "name": "Test Access Mobile User",
            "phone": "9900000001",
            "password": "test-password",
            "employee_id": cls.employee.id,
        })
        cls.empty_mobile_user = cls.MobileUser.create({
            "name": "Test Empty Mobile User",
            "phone": "9900000002",
            "password": "test-password",
            "employee_id": cls.empty_employee.id,
        })
        cls.no_group_mobile_user = cls.MobileUser.create({
            "name": "Test No Group Mobile User",
            "phone": "9900000003",
            "password": "test-password",
            "employee_id": cls.no_group_employee.id,
        })

    def test_require_ui_access_allows_effective_resource(self):
        self.assertTrue(require_ui_access(self.mobile_user, "test.access.screen"))
        self.assertTrue(require_ui_access(self.mobile_user, "test.access.action"))

    def test_require_ui_access_denies_missing_key(self):
        with self.assertRaises(AccessDenied):
            require_ui_access(self.mobile_user, "")

    def test_require_ui_access_denies_unknown_resource(self):
        with self.assertRaises(AccessDenied):
            require_ui_access(self.mobile_user, "test.unknown.action")

    def test_require_ui_access_denies_inactive_resource(self):
        with self.assertRaises(AccessDenied):
            require_ui_access(self.mobile_user, "test.inactive.action")

    def test_require_ui_access_denies_active_resource_without_module(self):
        with self.assertRaises(AccessDenied):
            require_ui_access(self.mobile_user, "test.unmapped.action")

    def test_require_ui_access_denies_hidden_resource(self):
        with self.assertRaises(AccessDenied):
            require_ui_access(self.mobile_user, "test.hidden.action")

    def test_require_ui_access_denies_group_without_grant(self):
        with self.assertRaises(AccessDenied):
            require_ui_access(self.empty_mobile_user, "test.access.action")

    def test_require_ui_access_denies_mobile_user_without_group(self):
        with self.assertRaises(AccessDenied):
            require_ui_access(self.no_group_mobile_user, "test.access.action")

    def test_require_any_ui_access_allows_one_granted_key(self):
        chosen = require_any_ui_access(
            self.mobile_user,
            ["test.unknown.action", "test.access.action"],
        )
        self.assertEqual(chosen, "test.access.action")

    def test_require_any_ui_access_denies_when_all_keys_fail(self):
        with self.assertRaises(AccessDenied):
            require_any_ui_access(
                self.mobile_user,
                ["test.unknown.action", "test.hidden.action"],
            )

    def test_sale_type_key_selects_primary_or_secondary(self):
        self.assertEqual(sale_type_key({"sale_type": "primary"}, "primary.key", "secondary.key"), "primary.key")
        self.assertEqual(sale_type_key({"sale_type": "secondary"}, "primary.key", "secondary.key"), "secondary.key")
        self.assertEqual(sale_type_key({}, "primary.key", "secondary.key"), "primary.key")

    def test_sale_type_key_rejects_invalid_type(self):
        with self.assertRaises(ValidationError):
            sale_type_key({"sale_type": "retail"}, "primary.key", "secondary.key")

    def test_require_sale_type_access_uses_selected_key(self):
        self.assertEqual(
            require_sale_type_access(
                self.mobile_user,
                {"sale_type": "primary"},
                "test.access.action",
                "test.hidden.action",
            ),
            "test.access.action",
        )
        with self.assertRaises(AccessDenied):
            require_sale_type_access(
                self.mobile_user,
                {"sale_type": "secondary"},
                "test.access.action",
                "test.hidden.action",
            )

    def test_contact_type_key_selects_distributor_or_outlet(self):
        self.assertEqual(
            contact_type_key({"customer_type": "distributor"}, "distributor.key", "outlet.key"),
            "distributor.key",
        )
        self.assertEqual(
            contact_type_key({"customer_type": "outlet"}, "distributor.key", "outlet.key"),
            "outlet.key",
        )

    def test_contact_type_key_rejects_invalid_type(self):
        with self.assertRaises(ValidationError):
            contact_type_key({"customer_type": "vendor"}, "distributor.key", "outlet.key")

    def test_require_contact_type_access_uses_selected_key(self):
        self.assertEqual(
            require_contact_type_access(
                self.mobile_user,
                {"customer_type": "distributor"},
                "test.access.action",
                "test.hidden.action",
            ),
            "test.access.action",
        )
        with self.assertRaises(AccessDenied):
            require_contact_type_access(
                self.mobile_user,
                {"customer_type": "outlet"},
                "test.access.action",
                "test.hidden.action",
            )

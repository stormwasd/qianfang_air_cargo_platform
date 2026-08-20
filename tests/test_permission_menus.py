import unittest

from app.core.permissions import validate_permissions
from app.utils.helpers import convert_permissions_to_codes
from app.utils.menu_mapping import generate_menus_by_permissions


class PermissionMenuTests(unittest.TestCase):
    FRONTEND_PERMISSION_CODES = [
        "organizational_management",
        "system",
        "customer_service",
        "expense_registration",
        "admin",
    ]

    def test_frontend_permission_codes_are_valid(self):
        self.assertTrue(validate_permissions(self.FRONTEND_PERMISSION_CODES))

    def test_invalid_permission_is_rejected(self):
        self.assertFalse(validate_permissions(["unknown_permission"]))

    def test_permission_names_are_normalized_to_frontend_codes(self):
        self.assertEqual(
            convert_permissions_to_codes(
                ["组织管理", "系统管理", "客服接单台", "费用登记台", "管理员"]
            ),
            self.FRONTEND_PERMISSION_CODES,
        )

    def test_each_frontend_permission_generates_its_menu(self):
        expected_menu_names = {
            "organizational_management": "组织管理",
            "system": "系统管理",
            "customer_service": "客服接单台",
            "expense_registration": "费用登记台",
        }

        for permission, expected_menu_name in expected_menu_names.items():
            with self.subTest(permission=permission):
                menus = generate_menus_by_permissions([permission])
                self.assertIn(expected_menu_name, [menu["name"] for menu in menus])
                self.assertIn("用户中心", [menu["name"] for menu in menus])

    def test_multiple_permissions_merge_menus_and_keep_user_center_last(self):
        permissions = self.FRONTEND_PERMISSION_CODES[:-1]
        menu_names = [
            menu["name"] for menu in generate_menus_by_permissions(permissions)
        ]
        self.assertEqual(
            menu_names,
            ["组织管理", "系统管理", "客服接单台", "费用登记台", "用户中心"],
        )

    def test_legacy_cost_service_permission_is_normalized(self):
        self.assertTrue(validate_permissions(["cost_service"]))
        self.assertEqual(
            convert_permissions_to_codes(["cost_service"]),
            ["expense_registration"],
        )
        self.assertEqual(
            generate_menus_by_permissions(["cost_service"]),
            generate_menus_by_permissions(["expense_registration"]),
        )

    def test_admin_receives_all_frontend_menus(self):
        menu_names = [
            menu["name"] for menu in generate_menus_by_permissions(["admin"])
        ]
        for expected_name in ["组织管理", "系统管理", "客服接单台", "费用登记台"]:
            self.assertIn(expected_name, menu_names)


if __name__ == "__main__":
    unittest.main()

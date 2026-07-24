import unittest
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.services.role_permission_service import (
    PAGE_CATALOG,
    action_allowed,
    permission_for,
    save_role_permissions,
)


class RolePermissionServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_admin_always_has_full_permissions(self):
        value = permission_for(self.db, "系统管理员", "/system/roles")
        self.assertTrue(value["can_view"])
        self.assertTrue(value["can_operate"])
        self.assertTrue(value["action_permissions"]["save"])

    def test_operation_permission_also_enables_view(self):
        permissions = [
            SimpleNamespace(
                page_key=key,
                can_view=False,
                can_operate=key == "/projects/ledger",
                actions=[
                    SimpleNamespace(action_key=action_key, allowed=key == "/projects/ledger")
                    for action_key, _action_name in actions
                ],
            )
            for key, _name, _group, actions in PAGE_CATALOG
        ]

        save_role_permissions(self.db, "技术员", permissions)

        value = permission_for(self.db, "技术员", "/projects/ledger")
        self.assertTrue(value["can_view"])
        self.assertTrue(value["can_operate"])
        self.assertTrue(all(value["action_permissions"].values()))

    def test_buttons_on_same_page_are_authorized_independently(self):
        permissions = [
            SimpleNamespace(
                page_key=key,
                can_view=key == "/projects/detection-tasks",
                can_operate=False,
                actions=[
                    SimpleNamespace(
                        action_key=action_key,
                        allowed=key == "/projects/detection-tasks" and action_key == "edit",
                    )
                    for action_key, _action_name in actions
                ],
            )
            for key, _name, _group, actions in PAGE_CATALOG
        ]
        save_role_permissions(self.db, "技术员", permissions)

        self.assertTrue(action_allowed(self.db, "技术员", "/projects/detection-tasks", "edit"))
        self.assertFalse(action_allowed(self.db, "技术员", "/projects/detection-tasks", "delete"))


if __name__ == "__main__":
    unittest.main()

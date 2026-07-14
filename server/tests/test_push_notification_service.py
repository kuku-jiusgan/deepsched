import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import AlertRule, Notification, User
from app.services.push_notification_service import push_by_rule


class PushNotificationServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_notify_roles_filter_contextual_recipients(self):
        admin = User(
            username="admin",
            display_name="系统管理员",
            role="系统管理员",
            is_active=True,
        )
        analyst = User(
            username="analyst",
            display_name="分析员",
            role="分析员",
            is_active=True,
        )
        disabled_analyst = User(
            username="disabled",
            display_name="停用分析员",
            role="分析员",
            is_active=False,
        )
        rule = AlertRule(
            name="仪器故障后移",
            rule_type="instrument_fault_reschedule",
            enabled=True,
            enable_site=True,
            enable_wecom=False,
            notify_roles='["分析员"]',
        )
        self.db.add_all([admin, analyst, disabled_analyst, rule])
        self.db.commit()

        sent = push_by_rule(
            self.db,
            "instrument_fault_reschedule",
            [admin, analyst, disabled_analyst],
            "测试通知",
            "测试内容",
        )
        self.db.flush()

        recipients = [
            item.user_name
            for item in self.db.query(Notification).order_by(Notification.id).all()
        ]
        self.assertEqual(sent, 1)
        self.assertEqual(recipients, ["analyst"])

    def test_project_manager_context_is_not_a_user_role(self):
        manager = User(
            username="manager",
            display_name="项目负责人",
            role="分析所所长",
            is_active=True,
        )
        rule = AlertRule(
            name="故障排程冲突",
            rule_type="instrument_fault_schedule_conflict",
            enabled=True,
            enable_site=True,
            enable_wecom=False,
            notify_roles='["项目负责人"]',
        )
        self.db.add_all([manager, rule])
        self.db.commit()

        sent = push_by_rule(
            self.db,
            "instrument_fault_schedule_conflict",
            [manager],
            "测试通知",
            "测试内容",
            context_roles=["项目负责人"],
        )
        self.db.flush()

        self.assertEqual(sent, 1)
        self.assertEqual(self.db.query(Notification).one().user_name, "manager")

    def test_empty_notify_roles_send_to_no_users(self):
        analyst = User(
            username="analyst",
            display_name="分析员",
            role="分析员",
            is_active=True,
        )
        rule = AlertRule(
            name="仪器故障后移",
            rule_type="instrument_fault_reschedule",
            enabled=True,
            enable_site=True,
            enable_wecom=False,
            notify_roles="[]",
        )
        self.db.add_all([analyst, rule])
        self.db.commit()

        sent = push_by_rule(
            self.db,
            "instrument_fault_reschedule",
            [analyst],
            "测试通知",
            "测试内容",
        )
        self.db.flush()

        self.assertEqual(sent, 0)
        self.assertEqual(self.db.query(Notification).count(), 0)


if __name__ == "__main__":
    unittest.main()
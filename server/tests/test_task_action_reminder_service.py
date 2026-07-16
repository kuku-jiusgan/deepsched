import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import AlertRule, Notification, Project, Task, TimeSlot, User
from app.services.task_action_reminder_service import scan_task_action_reminders


class TaskActionReminderServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.now = datetime(2026, 7, 16, 10, 0)
        self.assignee = User(
            id=1,
            username="analyst",
            display_name="任务负责人",
            role="分析员",
            is_active=True,
        )
        self.manager = User(
            id=2,
            username="manager",
            display_name="项目负责人",
            role="分析所所长",
            is_active=True,
        )
        self.project = Project(
            id=1,
            name="项目一",
            code="P-001",
            manager_id=self.manager.id,
        )
        self.task = Task(
            id=1,
            project_id=self.project.id,
            name="LCMS方法开发",
            task_type="FFKF_001",
            assignee_id=self.assignee.id,
            status="scheduled",
        )
        self.slot = TimeSlot(
            id=1,
            schedule_run_id="run-1",
            task_id=self.task.id,
            plan_start=self.now,
            plan_end=self.now + timedelta(hours=1),
            status="scheduled",
        )
        self.db.add_all([
            self.assignee,
            self.manager,
            self.project,
            self.task,
            self.slot,
            AlertRule(
                name="任务开始延迟",
                rule_type="task_start_delay",
                enabled=True,
                notify_roles='["项目负责人","分析员"]',
                threshold_minutes=0,
            ),
            AlertRule(
                name="任务结束延期",
                rule_type="task_end_delay",
                enabled=True,
                notify_roles='["项目负责人","分析员"]',
                threshold_minutes=0,
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_start_time_sends_once_to_assignee_and_manager(self):
        first = scan_task_action_reminders(self.db, self.now)
        second = scan_task_action_reminders(self.db, self.now + timedelta(minutes=1))

        site_notifications = self._site_notifications("task_start_delay")
        self.assertEqual(2, first["start_reminders"])
        self.assertEqual(0, second["start_reminders"])
        self.assertEqual({"analyst", "manager"}, {item.user_name for item in site_notifications})
        self.assertTrue(all("请点击开始" in item.title for item in site_notifications))

    def test_start_threshold_is_honored(self):
        self.db.query(AlertRule).filter(
            AlertRule.rule_type == "task_start_delay",
        ).one().threshold_minutes = 30
        self.db.commit()

        before = scan_task_action_reminders(self.db, self.now + timedelta(minutes=29))
        due = scan_task_action_reminders(self.db, self.now + timedelta(minutes=30))

        self.assertEqual(0, before["start_reminders"])
        self.assertEqual(2, due["start_reminders"])

    def test_started_task_only_receives_end_reminder_at_plan_end(self):
        self.task.status = "running"
        self.slot.status = "running"
        self.slot.actual_start = self.now
        self.db.commit()

        before = scan_task_action_reminders(self.db, self.slot.plan_end - timedelta(minutes=1))
        due = scan_task_action_reminders(self.db, self.slot.plan_end)

        self.assertEqual(0, before["end_reminders"])
        self.assertEqual(2, due["end_reminders"])
        self.assertEqual(0, len(self._site_notifications("task_start_delay")))
        self.assertTrue(all(
            "请点击结束" in item.title
            for item in self._site_notifications("task_end_delay")
        ))

    def test_unstarted_task_does_not_receive_end_reminder(self):
        result = scan_task_action_reminders(self.db, self.slot.plan_end)

        self.assertEqual(0, result["end_reminders"])

    def test_completed_task_does_not_receive_reminders(self):
        self.task.status = "done"
        self.slot.status = "completed"
        self.slot.actual_start = self.now
        self.slot.actual_end = self.slot.plan_end
        self.db.commit()

        result = scan_task_action_reminders(self.db, self.slot.plan_end)

        self.assertEqual({"start_reminders": 0, "end_reminders": 0}, result)
        self.assertEqual(0, self.db.query(Notification).count())

    def _site_notifications(self, reminder_type: str) -> list[Notification]:
        return self.db.query(Notification).filter(
            Notification.n_type == reminder_type,
            Notification.channel == "site",
        ).all()


if __name__ == "__main__":
    unittest.main()

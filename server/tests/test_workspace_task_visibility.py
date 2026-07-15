import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.schedules import _filter_workspace_tasks_by_user, _select_workspace_slot, _task_actual_window
from app.core.database import Base
from app.models import Project, Task, TimeSlot, User


class WorkspaceTaskVisibilityTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.admin = User(username="admin", display_name="系统管理员", role="系统管理员", is_active=True)
        self.owner = User(username="owner", display_name="李伟", role="分析员", is_active=True)
        self.other = User(username="other", display_name="陈婷婷", role="分析员", is_active=True)
        self.db.add_all([self.admin, self.owner, self.other])
        self.db.flush()

        project = Project(name="项目", code="XM-001", manager_id=self.owner.id)
        self.db.add(project)
        self.db.flush()

        self.owner_task = Task(
            project_id=project.id,
            name="负责人任务",
            task_type="FFKF_001",
            status="scheduled",
            assignee_id=self.owner.id,
        )
        self.other_task = Task(
            project_id=project.id,
            name="其他人任务",
            task_type="FFKF_001",
            status="scheduled",
            assignee_id=self.other.id,
        )
        self.db.add_all([self.owner_task, self.other_task])
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_system_admin_sees_all_workspace_tasks(self):
        query = _filter_workspace_tasks_by_user(self.db.query(Task), self.admin)

        self.assertEqual({self.owner_task.id, self.other_task.id}, {task.id for task in query.all()})

    def test_regular_user_only_sees_assigned_workspace_tasks(self):
        query = _filter_workspace_tasks_by_user(self.db.query(Task), self.owner)

        self.assertEqual([self.owner_task.id], [task.id for task in query.all()])

    def test_workspace_slot_uses_current_running_segment(self):
        past_slot = TimeSlot(
            task_id=self.owner_task.id,
            instrument_id=1,
            plan_start=datetime(2026, 7, 13, 19, 0),
            plan_end=datetime(2026, 7, 13, 22, 0),
            status="running",
        )
        today_slot = TimeSlot(
            task_id=self.owner_task.id,
            instrument_id=1,
            plan_start=datetime(2026, 7, 14, 8, 30),
            plan_end=datetime(2026, 7, 14, 22, 0),
            status="running",
        )
        future_slot = TimeSlot(
            task_id=self.owner_task.id,
            instrument_id=1,
            plan_start=datetime(2026, 7, 15, 8, 30),
            plan_end=datetime(2026, 7, 15, 12, 30),
            status="running",
        )

        selected = _select_workspace_slot(
            [past_slot, today_slot, future_slot],
            datetime(2026, 7, 14, 9, 0),
        )

        self.assertIs(today_slot, selected)

    def test_task_actual_window_uses_earliest_start_across_segments(self):
        started_at = datetime(2026, 7, 13, 19, 3, 58)
        slots = [
            TimeSlot(
                task_id=self.owner_task.id,
                instrument_id=1,
                plan_start=datetime(2026, 7, 13, 19, 0),
                plan_end=datetime(2026, 7, 13, 22, 0),
                actual_start=started_at,
                status="running",
            ),
            TimeSlot(
                task_id=self.owner_task.id,
                instrument_id=1,
                plan_start=datetime(2026, 7, 14, 8, 30),
                plan_end=datetime(2026, 7, 15, 6, 0),
                status="running",
            ),
            TimeSlot(
                task_id=self.owner_task.id,
                instrument_id=1,
                plan_start=datetime(2026, 7, 15, 8, 30),
                plan_end=datetime(2026, 7, 15, 12, 30),
                status="running",
            ),
        ]

        actual_start, actual_end = _task_actual_window(slots)

        self.assertEqual(started_at, actual_start)
        self.assertIsNone(actual_end)


if __name__ == "__main__":
    unittest.main()

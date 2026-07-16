import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Project, Task, TimeSlot
from app.services.schedule_reschedule_service import reschedule


class ScheduleRescheduleServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_global_reschedule_failure_restores_existing_schedule(self):
        project = Project(name="全局重排测试", code="GLOBAL-ROLLBACK")
        self.db.add(project)
        self.db.flush()
        task = Task(
            project_id=project.id,
            name="原排程任务",
            task_type="test",
            requires_human=False,
            status="scheduled",
        )
        self.db.add(task)
        self.db.flush()
        slot = TimeSlot(
            task_id=task.id,
            plan_start=datetime(2026, 8, 3, 8, 30),
            plan_end=datetime(2026, 8, 3, 9, 30),
            tier="confirmed",
            status="scheduled",
        )
        self.db.add(slot)
        self.db.commit()
        request = type("Request", (), {"strategy": "global"})()

        with patch(
            "app.services.scheduler.SchedulerService.generate",
            return_value={"status": "error", "message": "求解失败"},
        ):
            result = reschedule(self.db, request)

        self.assertEqual("error", result["status"])
        self.assertEqual("scheduled", self.db.get(Task, task.id).status)
        self.assertIsNotNone(self.db.get(TimeSlot, slot.id))


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Project, Task, TaskDependency, TimeSlot
from app.services.task_execution_service import (
    TaskExecutionInvalidError,
    start_task_execution,
)


class TaskExecutionServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.project = Project(id=1, name="项目", code="P-001")
        self.predecessor = Task(
            id=1,
            project_id=1,
            name="方法开发",
            task_type="FFKF_001",
            status="running",
        )
        self.task = Task(
            id=2,
            project_id=1,
            name="方案撰写",
            task_type="QCFA_001",
            status="scheduled",
        )
        self.slot = TimeSlot(
            id=1,
            task_id=2,
            plan_start=datetime.now() - timedelta(minutes=30),
            plan_end=datetime.now() + timedelta(minutes=30),
            status="scheduled",
            tier="confirmed",
        )
        self.db.add_all([self.project, self.predecessor, self.task, self.slot])
        self.db.add(TaskDependency(task_id=2, predecessor_id=1))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_incomplete_predecessor_blocks_start(self):
        with self.assertRaisesRegex(TaskExecutionInvalidError, "方法开发.*尚未完成"):
            start_task_execution(self.db, self.slot.id)

        self.assertEqual("scheduled", self.db.get(Task, self.task.id).status)

    def test_completed_predecessor_allows_start(self):
        self.predecessor.status = "done"
        self.db.commit()

        result = start_task_execution(self.db, self.slot.id)

        self.assertEqual("ok", result["status"])
        self.assertEqual("running", self.db.get(Task, self.task.id).status)
        self.assertEqual("running", self.db.get(TimeSlot, self.slot.id).status)
        self.assertIsNotNone(self.db.get(TimeSlot, self.slot.id).actual_start)

    def test_task_cannot_start_before_planned_time(self):
        self.predecessor.status = "done"
        self.slot.plan_start = datetime.now() + timedelta(hours=1)
        self.slot.plan_end = datetime.now() + timedelta(hours=2)
        self.db.commit()

        with self.assertRaisesRegex(TaskExecutionInvalidError, "不能提前启动"):
            start_task_execution(self.db, self.slot.id)

    def test_started_task_cannot_start_twice(self):
        self.predecessor.status = "done"
        self.slot.actual_start = datetime.now() - timedelta(minutes=10)
        self.slot.status = "running"
        self.task.status = "running"
        self.db.commit()

        with self.assertRaisesRegex(TaskExecutionInvalidError, "已经开始"):
            start_task_execution(self.db, self.slot.id)


if __name__ == "__main__":
    unittest.main()

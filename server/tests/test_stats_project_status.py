import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.stats import dashboard
from app.core.database import Base
from app.models import Project, Task, TimeSlot


class StatsProjectStatusTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_dashboard_ignores_stale_active_project_column(self):
        project = Project(id=1, name="未启动项目", code="P-001", status="active")
        task = Task(
            id=1,
            project_id=1,
            name="等待验证",
            task_type="test",
            status="waiting_external",
        )
        self.db.add_all([project, task])
        self.db.commit()

        now = datetime.now()
        result = dashboard(now - timedelta(days=1), now, self.db)

        self.assertEqual(1, result.total_projects)
        self.assertEqual(0, result.active_projects)

    def test_dashboard_counts_project_with_actual_start_as_active(self):
        project = Project(id=1, name="已启动项目", code="P-001", status="pending")
        task = Task(id=1, project_id=1, name="方法开发", task_type="test", status="scheduled")
        now = datetime.now()
        slot = TimeSlot(
            task_id=1,
            instrument_id=None,
            plan_start=now - timedelta(hours=2),
            plan_end=now + timedelta(hours=2),
            actual_start=now - timedelta(hours=1),
            status="running",
        )
        self.db.add_all([project, task, slot])
        self.db.commit()

        result = dashboard(now - timedelta(days=1), now, self.db)

        self.assertEqual(1, result.active_projects)


if __name__ == "__main__":
    unittest.main()

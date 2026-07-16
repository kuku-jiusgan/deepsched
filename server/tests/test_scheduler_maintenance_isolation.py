import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Instrument, MaintenanceWindow, Project, Task, TimeSlot
from app.services.scheduler import SchedulerService


class SchedulerMaintenanceIsolationTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.horizon_start = datetime(2026, 8, 3, 8, 30)

    def tearDown(self):
        self.db.close()

    def test_maintenance_only_blocks_its_own_instrument(self):
        project = Project(
            name="维护隔离测试",
            code="MAINT-ISOLATION",
            estimated_hours=10,
            start_date=self.horizon_start,
            end_date=self.horizon_start + timedelta(days=5),
        )
        maintained = Instrument(
            code="MAINT-A",
            name="维护仪器A",
            availability_status="available",
            status="idle",
        )
        available = Instrument(
            code="MAINT-B",
            name="可用仪器B",
            availability_status="available",
            status="idle",
        )
        self.db.add_all([project, maintained, available])
        self.db.flush()
        self.db.add(MaintenanceWindow(
            instrument_id=maintained.id,
            start_time=self.horizon_start,
            end_time=self.horizon_start + timedelta(hours=4),
            mw_type="maintenance",
        ))
        task = Task(
            project_id=project.id,
            name="指定B仪器任务",
            task_type="test",
            requires_instrument=True,
            requires_human=False,
            est_duration_hours=1,
            instrument_ids=[available.id],
            status="pending",
        )
        self.db.add(task)
        self.db.flush()

        total_units = 10 * 48
        with patch(
            "app.services.scheduler.time_horizon",
            return_value=(
                self.horizon_start,
                self.horizon_start + timedelta(days=10),
                total_units,
            ),
        ):
            result = SchedulerService(self.db).generate(
                project_ids=[project.id],
                commit=False,
            )

        slot = self.db.query(TimeSlot).filter(TimeSlot.task_id == task.id).one()
        self.assertEqual("ok", result["status"])
        self.assertEqual(available.id, slot.instrument_id)
        self.assertEqual(self.horizon_start, slot.plan_start)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.schedules import _latest_open_task_slot
from app.core.database import Base
from app.models import Task, TimeSlot


class ScheduleAutoDelayTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_latest_open_slot_uses_final_task_end(self):
        task = Task(project_id=1, name="multi-slot", task_type="test", status="scheduled")
        self.db.add(task)
        self.db.flush()
        self.db.add_all([
            TimeSlot(
                task_id=task.id,
                instrument_id=1,
                plan_start=datetime(2026, 7, 12, 19, 0),
                plan_end=datetime(2026, 7, 12, 20, 0),
                status="scheduled",
            ),
            TimeSlot(
                task_id=task.id,
                instrument_id=1,
                plan_start=datetime(2026, 7, 14, 8, 30),
                plan_end=datetime(2026, 7, 14, 18, 30),
                status="scheduled",
            ),
        ])
        self.db.commit()

        slot = _latest_open_task_slot(task.id, self.db)

        self.assertEqual(datetime(2026, 7, 14, 18, 30), slot.plan_end)


if __name__ == "__main__":
    unittest.main()

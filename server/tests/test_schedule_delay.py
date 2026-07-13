import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Task, TimeSlot
from app.services.schedule_delay_service import report_task_delay


class ScheduleDelayTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_delay_from_current_card_extends_final_task_slot(self):
        task = Task(project_id=1, name="multi-day", task_type="test", status="scheduled")
        self.db.add(task)
        self.db.flush()
        current_slot = TimeSlot(
            task_id=task.id, instrument_id=1,
            plan_start=datetime(2026, 7, 13, 8, 30),
            plan_end=datetime(2026, 7, 13, 20, 0), status="scheduled",
        )
        final_slot = TimeSlot(
            task_id=task.id, instrument_id=1,
            plan_start=datetime(2026, 7, 14, 8, 30),
            plan_end=datetime(2026, 7, 14, 18, 30), status="scheduled",
        )
        self.db.add_all([current_slot, final_slot])
        self.db.commit()

        result = report_task_delay(self.db, current_slot.id, 2, "实验延迟")

        self.db.refresh(current_slot)
        self.db.refresh(final_slot)
        self.assertEqual(datetime(2026, 7, 13, 20, 0), current_slot.plan_end)
        self.assertEqual(datetime(2026, 7, 14, 20, 30), final_slot.plan_end)
        self.assertEqual(final_slot.id, result["slot_id"])


if __name__ == "__main__":
    unittest.main()

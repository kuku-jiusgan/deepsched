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
        task_slots = self.db.query(TimeSlot).filter(
            TimeSlot.task_id == task.id,
        ).order_by(TimeSlot.plan_start).all()
        self.assertEqual(datetime(2026, 7, 13, 20, 0), current_slot.plan_end)
        self.assertEqual(datetime(2026, 7, 14, 20, 0), final_slot.plan_end)
        self.assertEqual(datetime(2026, 7, 15, 8, 30), task_slots[-1].plan_start)
        self.assertEqual(datetime(2026, 7, 15, 9, 0), task_slots[-1].plan_end)
        self.assertEqual(final_slot.id, result["slot_id"])
        self.db.refresh(task)
        self.assertEqual("delayed", task.delay_status)

    def test_following_task_delay_respects_working_hours(self):
        delayed_task = Task(project_id=1, name="delayed", task_type="test", status="scheduled")
        following_task = Task(project_id=1, name="following", task_type="test", status="scheduled")
        self.db.add_all([delayed_task, following_task])
        self.db.flush()
        delayed_slot = TimeSlot(
            task_id=delayed_task.id, instrument_id=1,
            plan_start=datetime(2026, 7, 13, 8, 30),
            plan_end=datetime(2026, 7, 13, 18, 30), status="scheduled",
        )
        following_slot = TimeSlot(
            task_id=following_task.id, instrument_id=1,
            plan_start=datetime(2026, 7, 13, 18, 30),
            plan_end=datetime(2026, 7, 13, 20, 0), status="scheduled",
        )
        self.db.add_all([delayed_slot, following_slot])
        self.db.commit()

        report_task_delay(self.db, delayed_slot.id, 2, "实验延迟")

        shifted_slots = self.db.query(TimeSlot).filter(
            TimeSlot.task_id == following_task.id,
            TimeSlot.status == "scheduled",
        ).order_by(TimeSlot.plan_start).all()
        self.assertEqual(1, len(shifted_slots))
        self.assertEqual(datetime(2026, 7, 14, 9, 0), shifted_slots[0].plan_start)
        self.assertEqual(datetime(2026, 7, 14, 10, 30), shifted_slots[0].plan_end)


if __name__ == "__main__":
    unittest.main()

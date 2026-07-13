import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Task, TaskDependency, TimeSlot
from app.services.schedule_completion_service import (
    _mark_task_slots_completed,
    _select_completed_slot,
)


class ScheduleCompletionTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_complete_multi_day_task_preserves_plan_boundaries(self):
        task = Task(project_id=1, name="multi-day", task_type="test", status="running")
        self.db.add(task)
        self.db.flush()
        slots = [
            TimeSlot(
                task_id=task.id, instrument_id=1,
                plan_start=datetime(2026, 7, 10, 17, 30),
                plan_end=datetime(2026, 7, 10, 20, 0), status="running",
            ),
            TimeSlot(
                task_id=task.id, instrument_id=1,
                plan_start=datetime(2026, 7, 11, 8, 30),
                plan_end=datetime(2026, 7, 11, 20, 0), status="scheduled",
            ),
            TimeSlot(
                task_id=task.id, instrument_id=1,
                plan_start=datetime(2026, 7, 12, 8, 30),
                plan_end=datetime(2026, 7, 12, 17, 0), status="scheduled",
            ),
        ]
        self.db.add_all(slots)
        self.db.commit()
        original_ranges = [(slot.plan_start, slot.plan_end) for slot in slots]
        end_time = datetime(2026, 7, 13, 9, 23)

        completed_slot = _select_completed_slot(slots, slots[0].id, end_time)
        _mark_task_slots_completed(slots, completed_slot, end_time)

        self.assertEqual(slots[-1].id, completed_slot.id)
        self.assertEqual(original_ranges, [(slot.plan_start, slot.plan_end) for slot in slots])
        self.assertTrue(all(slot.status == "completed" for slot in slots))
        self.assertEqual(end_time, slots[-1].actual_end)
        self.assertEqual(datetime(2026, 7, 10, 20, 0), slots[0].actual_end)
        self.assertEqual(datetime(2026, 7, 11, 20, 0), slots[1].actual_end)

    def test_future_segments_complete_without_fake_actual_times(self):
        slots = [
            TimeSlot(
                id=1, task_id=1, instrument_id=1,
                plan_start=datetime(2026, 7, 13, 8, 30),
                plan_end=datetime(2026, 7, 13, 20, 0), status="running",
            ),
            TimeSlot(
                id=2, task_id=1, instrument_id=1,
                plan_start=datetime(2026, 7, 14, 8, 30),
                plan_end=datetime(2026, 7, 14, 18, 30), status="scheduled",
            ),
        ]
        end_time = datetime(2026, 7, 13, 10, 0)

        _mark_task_slots_completed(slots, slots[0], end_time)

        self.assertEqual("completed", slots[1].status)
        self.assertIsNone(slots[1].actual_start)
        self.assertIsNone(slots[1].actual_end)
        self.assertEqual(datetime(2026, 7, 14, 18, 30), slots[1].plan_end)

    def test_completed_future_segments_do_not_block_forward_shift(self):
        completed = Task(project_id=1, name="done", task_type="test", status="done")
        next_task = Task(project_id=1, name="next", task_type="test", status="scheduled")
        self.db.add_all([completed, next_task])
        self.db.flush()
        self.db.add(TaskDependency(task_id=next_task.id, predecessor_id=completed.id))
        self.db.add_all([
            TimeSlot(
                task_id=completed.id, instrument_id=1,
                plan_start=datetime(2026, 7, 13, 8, 30),
                plan_end=datetime(2026, 7, 13, 20, 0),
                actual_start=datetime(2026, 7, 13, 8, 30),
                actual_end=datetime(2026, 7, 13, 12, 0),
                status="completed",
            ),
            TimeSlot(
                task_id=completed.id, instrument_id=1,
                plan_start=datetime(2026, 7, 14, 8, 30),
                plan_end=datetime(2026, 7, 14, 20, 0),
                status="completed",
            ),
            TimeSlot(
                task_id=next_task.id, instrument_id=1,
                plan_start=datetime(2026, 7, 15, 8, 30),
                plan_end=datetime(2026, 7, 15, 10, 30),
                status="scheduled",
            ),
        ])
        self.db.commit()

        from app.services import schedule_completion_service as service

        service._load_working_options = lambda db, released_at: {
            "day_start_minutes": 8 * 60 + 30,
            "day_end_minutes": 20 * 60,
            "include_weekends": True,
            "include_holidays": True,
            "horizon_end": datetime(2026, 7, 20),
            "calendar_days": {},
        }
        result = service._forward_shift_same_project_work(
            self.db, completed, 1, datetime(2026, 7, 13, 12, 0)
        )

        moved_slot = self.db.query(TimeSlot).filter(
            TimeSlot.task_id == next_task.id,
            TimeSlot.status == "scheduled",
        ).one()
        self.assertEqual(1, result["moved_tasks"])
        self.assertEqual(datetime(2026, 7, 13, 12, 0), moved_slot.plan_start)
        self.assertEqual(datetime(2026, 7, 13, 14, 0), moved_slot.plan_end)


if __name__ == "__main__":
    unittest.main()

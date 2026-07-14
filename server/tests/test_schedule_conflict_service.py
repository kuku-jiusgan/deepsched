import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import TimeSlot
from app.services.schedule_conflict_service import find_instrument_conflicts


class ScheduleConflictServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_unexecuted_completed_segments_do_not_create_conflicts(self):
        completed_future = TimeSlot(
            task_id=1, instrument_id=1,
            plan_start=datetime(2026, 7, 16, 8, 30),
            plan_end=datetime(2026, 7, 16, 17, 30),
            status="completed",
        )
        scheduled = TimeSlot(
            task_id=2, instrument_id=1,
            plan_start=datetime(2026, 7, 16, 14, 30),
            plan_end=datetime(2026, 7, 16, 20, 0),
            status="scheduled",
        )
        self.db.add_all([completed_future, scheduled])
        self.db.commit()

        self.assertEqual([], find_instrument_conflicts(self.db))

    def test_completed_segments_use_actual_time_for_conflicts(self):
        completed = TimeSlot(
            task_id=1, instrument_id=1,
            plan_start=datetime(2026, 7, 16, 8, 30),
            plan_end=datetime(2026, 7, 16, 17, 30),
            actual_start=datetime(2026, 7, 16, 8, 30),
            actual_end=datetime(2026, 7, 16, 12, 30),
            status="completed",
        )
        scheduled = TimeSlot(
            task_id=2, instrument_id=1,
            plan_start=datetime(2026, 7, 16, 14, 30),
            plan_end=datetime(2026, 7, 16, 20, 0),
            status="scheduled",
        )
        self.db.add_all([completed, scheduled])
        self.db.commit()

        self.assertEqual([], find_instrument_conflicts(self.db))


if __name__ == "__main__":
    unittest.main()

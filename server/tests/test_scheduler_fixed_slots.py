import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import TimeSlot
from app.services.scheduler_fixed_slots import load_fixed_slots


class SchedulerFixedSlotsTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_unexecuted_completed_segments_are_not_fixed(self):
        executed = TimeSlot(
            task_id=1, instrument_id=1,
            plan_start=datetime(2026, 7, 13, 8, 30),
            plan_end=datetime(2026, 7, 13, 20, 0),
            actual_start=datetime(2026, 7, 13, 8, 30),
            actual_end=datetime(2026, 7, 13, 12, 0),
            status="completed",
        )
        unexecuted = TimeSlot(
            task_id=1, instrument_id=1,
            plan_start=datetime(2026, 7, 14, 8, 30),
            plan_end=datetime(2026, 7, 14, 20, 0),
            status="completed",
        )
        scheduled = TimeSlot(
            task_id=2, instrument_id=1,
            plan_start=datetime(2026, 7, 15, 8, 30),
            plan_end=datetime(2026, 7, 15, 10, 0),
            status="scheduled",
        )
        self.db.add_all([executed, unexecuted, scheduled])
        self.db.commit()

        fixed_slots = load_fixed_slots(self.db)

        self.assertEqual({executed.id, scheduled.id}, {slot.id for slot in fixed_slots})


if __name__ == "__main__":
    unittest.main()

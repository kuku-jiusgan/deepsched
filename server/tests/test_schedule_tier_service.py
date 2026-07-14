import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import ScheduleRule, TimeSlot
from app.services.schedule_rule_service import get_solver_constraints
from app.services.schedule_tier_service import roll_schedule_tiers


class ScheduleTierServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        get_solver_constraints(self.db)
        freezing = self.db.query(ScheduleRule).filter(ScheduleRule.code == "freezing").one()
        freezing.params = {"freeze_days": 1, "strict": True}
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_roll_recalculates_frozen_tiers_by_natural_day(self):
        today_slot = TimeSlot(
            task_id=1, plan_start=datetime(2026, 7, 13, 22, 0),
            plan_end=datetime(2026, 7, 13, 23, 0), tier="confirmed", status="scheduled",
        )
        tomorrow_slot = TimeSlot(
            task_id=2, plan_start=datetime(2026, 7, 14, 8, 30),
            plan_end=datetime(2026, 7, 14, 10, 0), tier="frozen", status="scheduled",
        )
        running_slot = TimeSlot(
            task_id=3, plan_start=datetime(2026, 7, 14, 8, 30),
            plan_end=datetime(2026, 7, 14, 10, 0), tier="frozen", status="running",
        )
        self.db.add_all([today_slot, tomorrow_slot, running_slot])
        self.db.commit()

        roll_schedule_tiers(self.db, datetime(2026, 7, 13, 13, 0))

        self.db.refresh(today_slot)
        self.db.refresh(tomorrow_slot)
        self.db.refresh(running_slot)
        self.assertEqual("frozen", today_slot.tier)
        self.assertEqual("confirmed", tomorrow_slot.tier)
        self.assertEqual("frozen", running_slot.tier)


if __name__ == "__main__":
    unittest.main()

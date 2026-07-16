import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Instrument, Project, Task, TimeSlot
from app.services.instrument_status_service import delete_time_slots_and_refresh


class InstrumentStatusRefreshTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_deleting_last_running_slot_refreshes_instrument_to_idle(self):
        slot = self._create_running_slot()

        delete_time_slots_and_refresh(
            self.db,
            self.db.query(TimeSlot).filter(TimeSlot.id == slot.id),
        )

        instrument = self.db.query(Instrument).filter(Instrument.id == 1).one()
        self.assertEqual("idle", instrument.status)

    def test_deleting_one_running_slot_keeps_instrument_running_when_another_remains(self):
        first_slot = self._create_running_slot()
        second_task = Task(
            id=2,
            project_id=1,
            name="连续运行",
            task_type="TEST_002",
            status="running",
        )
        second_slot = TimeSlot(
            task_id=2,
            instrument_id=1,
            plan_start=datetime.now(),
            plan_end=datetime.now() + timedelta(hours=2),
            actual_start=datetime.now(),
            status="running",
        )
        self.db.add_all([second_task, second_slot])
        self.db.commit()

        delete_time_slots_and_refresh(
            self.db,
            self.db.query(TimeSlot).filter(TimeSlot.id == first_slot.id),
        )

        instrument = self.db.query(Instrument).filter(Instrument.id == 1).one()
        self.assertEqual("running", instrument.status)

    def _create_running_slot(self) -> TimeSlot:
        now = datetime.now()
        project = Project(id=1, name="状态刷新项目", code="XM-STATUS")
        instrument = Instrument(
            id=1,
            code="ZBYY-002-0011",
            name="三重四极液质联用仪",
            status="running",
        )
        task = Task(
            id=1,
            project_id=1,
            name="方法开发",
            task_type="TEST_001",
            status="running",
        )
        slot = TimeSlot(
            id=1,
            task_id=1,
            instrument_id=1,
            plan_start=now,
            plan_end=now + timedelta(hours=1),
            actual_start=now,
            status="running",
        )
        self.db.add_all([project, instrument, task, slot])
        self.db.commit()
        return slot


if __name__ == "__main__":
    unittest.main()

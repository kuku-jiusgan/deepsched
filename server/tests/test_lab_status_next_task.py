import unittest
from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.stats import lab_status
from app.core.database import Base
from app.models import Instrument, Project, Task, TimeSlot, User


class LabStatusNextTaskTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_next_task_includes_project_and_assignee(self):
        now = datetime.now()
        user = User(id=1, username="analyst", display_name="张分析", role="分析员")
        project = Project(id=1, name="杂质研究项目", code="XM-001", manager_id=1)
        instrument = Instrument(id=1, code="LCMS-01", name="液质联用仪", status="idle")
        task = Task(
            id=1,
            project_id=1,
            name="方法验证",
            task_type="FFYZ_001",
            assignee_id=1,
            status="scheduled",
        )
        slot = TimeSlot(
            task_id=1,
            instrument_id=1,
            plan_start=now + timedelta(hours=1),
            plan_end=now + timedelta(hours=5),
            status="scheduled",
        )
        self.db.add_all([user, project, instrument, task, slot])
        self.db.commit()

        item = lab_status(self.db)[0]

        self.assertEqual("方法验证", item["next_task"])
        self.assertEqual("杂质研究项目", item["next_project"])
        self.assertEqual("XM-001", item["next_project_code"])
        self.assertEqual("张分析", item["next_user"])


if __name__ == "__main__":
    unittest.main()

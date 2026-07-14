import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Project
from app.schemas.schemas import ProjectCreate
from app.services.project_plan_change_service import PlanChangeInvalidError, update_project_plan
from app.services.project_service import ProjectCodeExistsError, create_project


class ProjectServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_create_project_rejects_duplicate_code(self):
        self.db.add(Project(name="已有项目", code="PRJ-001", priority=1))
        self.db.commit()

        with self.assertRaisesRegex(ProjectCodeExistsError, "项目编号 PRJ-001 已存在"):
            create_project(
                self.db,
                ProjectCreate(name="新项目", code="PRJ-001", priority=2),
            )

        self.assertEqual(1, self.db.query(Project).count())

    def test_update_project_rejects_another_project_code(self):
        first = Project(name="项目一", code="PRJ-001", priority=1)
        second = Project(name="项目二", code="PRJ-002", priority=2)
        self.db.add_all([first, second])
        self.db.commit()

        with self.assertRaisesRegex(PlanChangeInvalidError, "项目编号 PRJ-001 已存在"):
            update_project_plan(
                self.db,
                second.id,
                ProjectCreate(name="项目二", code=" PRJ-001 ", priority=2),
            )

    def test_create_project_trims_name_and_code(self):
        project = create_project(
            self.db,
            ProjectCreate(name="  新项目  ", code="  PRJ-002  ", priority=3),
        )

        self.assertEqual("新项目", project.name)
        self.assertEqual("PRJ-002", project.code)

    def test_update_project_accepts_timezone_dates_when_only_hours_change(self):
        project = Project(
            name="项目",
            code="PRJ-003",
            priority=1,
            start_date=datetime(2026, 7, 14, 0, 0),
            end_date=datetime(2026, 7, 20, 0, 0),
        )
        self.db.add(project)
        self.db.commit()

        updated = update_project_plan(
            self.db,
            project.id,
            ProjectCreate(
                name="项目",
                code="PRJ-003",
                priority=1,
                estimated_hours=40,
                start_date=datetime(2026, 7, 14, 0, 0, tzinfo=timezone.utc),
                end_date=datetime(2026, 7, 20, 0, 0, tzinfo=timezone.utc),
            ),
        )

        self.assertEqual(40, updated.estimated_hours)
        self.assertIsNone(updated.start_date.tzinfo)


if __name__ == "__main__":
    unittest.main()

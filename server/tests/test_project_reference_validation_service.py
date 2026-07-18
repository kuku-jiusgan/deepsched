import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Instrument, Milestone, Project, Task, User
from app.services.project_reference_validation_service import (
    ProjectReferenceInvalidError,
    validate_task_references,
)


class ProjectReferenceValidationServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.active_user = User(
            username="active", display_name="启用用户", role="分析员", is_active=True
        )
        self.disabled_user = User(
            username="disabled", display_name="停用用户", role="分析员", is_active=False
        )
        self.db.add_all([self.active_user, self.disabled_user])
        self.db.flush()
        self.first_project = Project(name="项目一", code="P-REF-1")
        self.second_project = Project(name="项目二", code="P-REF-2")
        self.db.add_all([self.first_project, self.second_project])
        self.db.flush()
        self.first_task = Task(
            project_id=self.first_project.id, name="任务一", task_type="manual"
        )
        self.second_task = Task(
            project_id=self.second_project.id, name="任务二", task_type="manual"
        )
        self.first_milestone = Milestone(
            project_id=self.first_project.id, name="里程碑一", due_date=datetime.now()
        )
        self.second_milestone = Milestone(
            project_id=self.second_project.id, name="里程碑二", due_date=datetime.now()
        )
        self.instrument = Instrument(code="I-REF", name="仪器")
        self.db.add_all(
            [
                self.first_task,
                self.second_task,
                self.first_milestone,
                self.second_milestone,
                self.instrument,
            ]
        )
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_valid_same_project_references_are_accepted(self):
        validate_task_references(
            self.db,
            self.first_project.id,
            parent_id=self.first_task.id,
            milestone_id=self.first_milestone.id,
            predecessor_ids=[self.first_task.id],
            assignee_id=self.active_user.id,
            instrument_ids=[self.instrument.id],
        )

    def test_cross_project_parent_predecessor_and_milestone_are_rejected(self):
        cases = [
            {"parent_id": self.second_task.id},
            {"predecessor_ids": [self.second_task.id]},
            {"milestone_id": self.second_milestone.id},
        ]
        for overrides in cases:
            values = {
                "parent_id": None,
                "milestone_id": None,
                "predecessor_ids": [],
                "assignee_id": self.active_user.id,
                "instrument_ids": [],
                **overrides,
            }
            with self.subTest(overrides=overrides), self.assertRaises(
                ProjectReferenceInvalidError
            ):
                validate_task_references(self.db, self.first_project.id, **values)

    def test_disabled_assignee_and_unknown_instrument_are_rejected(self):
        for values in [
            {"assignee_id": self.disabled_user.id, "instrument_ids": []},
            {"assignee_id": self.active_user.id, "instrument_ids": [999_999]},
        ]:
            with self.subTest(values=values), self.assertRaises(
                ProjectReferenceInvalidError
            ):
                validate_task_references(
                    self.db,
                    self.first_project.id,
                    parent_id=None,
                    milestone_id=None,
                    predecessor_ids=[],
                    **values,
                )


if __name__ == "__main__":
    unittest.main()

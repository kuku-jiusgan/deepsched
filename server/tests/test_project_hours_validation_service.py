import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Project, Task
from app.schemas.schemas import TaskUpdate
from app.services.project_hours_validation_service import (
    ProjectHoursExceededError,
    project_top_level_task_hours,
    validate_project_estimated_hours,
)
from app.services.project_plan_change_service import PlanChangeInvalidError, update_task_plan
from app.services.project_task_rollup_service import recalculate_project_parent_hours


class ProjectHoursValidationServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()

    def tearDown(self):
        self.db.close()

    def test_project_hours_only_counts_top_level_tasks(self):
        project = Project(name="项目", code="HOURS-001", estimated_hours=20)
        self.db.add(project)
        self.db.flush()
        parent = Task(project_id=project.id, name="父任务", task_type="test", est_duration_hours=15)
        child = Task(project_id=project.id, name="子任务", task_type="test", est_duration_hours=15, parent=parent)
        another_top = Task(project_id=project.id, name="顶级任务", task_type="test", est_duration_hours=5)
        self.db.add_all([parent, child, another_top])
        self.db.flush()

        self.assertEqual(20, project_top_level_task_hours(self.db, project.id))
        validate_project_estimated_hours(self.db, project.id)

    def test_validation_rejects_top_level_total_over_project_hours(self):
        project = Project(name="项目", code="HOURS-002", estimated_hours=10)
        self.db.add(project)
        self.db.flush()
        self.db.add_all([
            Task(project_id=project.id, name="任务一", task_type="test", est_duration_hours=8),
            Task(project_id=project.id, name="任务二", task_type="test", est_duration_hours=3),
        ])
        self.db.flush()

        with self.assertRaisesRegex(ProjectHoursExceededError, "已超过项目预计工时"):
            validate_project_estimated_hours(self.db, project.id)

    def test_updating_child_recalculates_parent_and_rejects_over_limit(self):
        project = Project(name="项目", code="HOURS-003", estimated_hours=20)
        self.db.add(project)
        self.db.flush()
        parent = Task(project_id=project.id, name="父任务", task_type="test", est_duration_hours=16)
        child_one = Task(project_id=project.id, name="子任务一", task_type="test", est_duration_hours=8, parent=parent)
        child_two = Task(project_id=project.id, name="子任务二", task_type="test", est_duration_hours=8, parent=parent)
        self.db.add_all([parent, child_one, child_two])
        self.db.commit()

        with self.assertRaisesRegex(PlanChangeInvalidError, "已超过项目预计工时"):
            update_task_plan(self.db, child_two.id, TaskUpdate(est_duration_hours=13))

        self.db.rollback()
        recalculate_project_parent_hours(self.db, project.id)
        self.db.refresh(parent)
        self.assertEqual(16, parent.est_duration_hours)


if __name__ == "__main__":
    unittest.main()

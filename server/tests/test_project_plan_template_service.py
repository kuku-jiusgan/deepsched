import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models import Project, Task, TaskDependency, TaskTypeConfig, User
from app.services.project_plan_template_service import (
    ProjectPlanTemplateInvalidError,
    ProjectPlanTemplatePermissionError,
    import_standard_plan,
)


class ProjectPlanTemplateServiceTest(unittest.TestCase):
    def setUp(self):
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        self.manager = User(id=1, username="manager", display_name="项目负责人", role="分析员")
        self.other_user = User(id=2, username="other", display_name="其他人员", role="分析员")
        self.project = Project(
            id=1,
            name="标准项目",
            code="TPL-001",
            estimated_hours=123.45,
            manager_id=1,
        )
        self.db.add_all([self.manager, self.other_user, self.project])
        for index, code in enumerate(["FFKF_001", "QCFA_001", "FFYZ_001", "ZXBG_001"]):
            self.db.add(TaskTypeConfig(
                name=code,
                code=code,
                resource_type="both",
                is_active=True,
                sort_order=index,
            ))
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_import_creates_standard_chain_with_exact_project_hours(self):
        result = import_standard_plan(self.db, self.project.id, self.manager)

        tasks = self.db.query(Task).filter(Task.project_id == self.project.id).all()
        by_name = {task.name: task for task in tasks}
        dependencies = {
            (dependency.predecessor_id, dependency.task_id)
            for dependency in self.db.query(TaskDependency).all()
        }
        work_tasks = [task for task in tasks if not task.is_external_gate]

        self.assertEqual(5, len(tasks))
        self.assertAlmostEqual(123.45, sum(task.est_duration_hours or 0 for task in work_tasks))
        self.assertEqual([70.0, 5.0, 20.0, 5.0], [task.percentage for task in result.tasks[:4]])
        self.assertIsNone(by_name["方案签批"].est_duration_hours)
        self.assertEqual(self.project.manager_id, by_name["方案签批"].assignee_id)
        self.assertEqual("waiting_external", by_name["方法验证"].status)
        self.assertEqual("waiting_external", by_name["报告撰写"].status)
        self.assertIn((by_name["方法开发"].id, by_name["方案撰写"].id), dependencies)
        self.assertIn((by_name["方案撰写"].id, by_name["方案签批"].id), dependencies)
        self.assertIn((by_name["方案签批"].id, by_name["方法验证"].id), dependencies)
        self.assertIn((by_name["方法验证"].id, by_name["报告撰写"].id), dependencies)

    def test_existing_plan_cannot_be_imported_twice(self):
        import_standard_plan(self.db, self.project.id, self.manager)

        with self.assertRaises(ProjectPlanTemplateInvalidError):
            import_standard_plan(self.db, self.project.id, self.manager)

    def test_non_manager_cannot_import_template(self):
        with self.assertRaises(ProjectPlanTemplatePermissionError):
            import_standard_plan(self.db, self.project.id, self.other_user)

    def test_project_requires_estimated_hours(self):
        self.project.estimated_hours = None
        self.db.commit()

        with self.assertRaises(ProjectPlanTemplateInvalidError):
            import_standard_plan(self.db, self.project.id, self.manager)


if __name__ == "__main__":
    unittest.main()

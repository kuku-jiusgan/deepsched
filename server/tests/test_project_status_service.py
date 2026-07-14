import unittest

from app.models import Project, Task
from app.services.project_status_service import calculate_project_status


class ProjectStatusServiceTest(unittest.TestCase):
    def test_project_without_started_tasks_is_pending(self):
        project = Project(tasks=[
            Task(id=1, name="待排", task_type="test", status="pending"),
            Task(id=2, name="已排程", task_type="test", status="scheduled"),
        ])

        self.assertEqual("pending", calculate_project_status(project))

    def test_project_with_started_task_is_active(self):
        project = Project(tasks=[
            Task(id=1, name="已完成", task_type="test", status="completed"),
            Task(id=2, name="待排", task_type="test", status="pending"),
        ])

        self.assertEqual("active", calculate_project_status(project))

    def test_project_with_all_leaf_tasks_completed_is_completed(self):
        project = Project(tasks=[
            Task(id=1, name="父任务", task_type="test", status="pending"),
            Task(id=2, name="子任务一", task_type="test", status="completed", parent_id=1),
            Task(id=3, name="子任务二", task_type="test", status="done", parent_id=1),
        ])

        self.assertEqual("completed", calculate_project_status(project))


if __name__ == "__main__":
    unittest.main()

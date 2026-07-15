import unittest
from datetime import datetime

from app.models import Project, Task, TimeSlot
from app.services.project_status_service import calculate_project_status


class ProjectStatusServiceTest(unittest.TestCase):
    def test_project_without_started_tasks_is_pending(self):
        project = Project(tasks=[
            Task(id=1, name="待排", task_type="test", status="pending"),
            Task(id=2, name="已排程", task_type="test", status="scheduled"),
        ])

        self.assertEqual("pending", calculate_project_status(project))

    def test_external_waiting_tasks_do_not_start_project(self):
        project = Project(tasks=[
            Task(id=1, name="方法开发", task_type="test", status="pending"),
            Task(id=2, name="方案签批", task_type="approval_gate", status="waiting_external"),
            Task(id=3, name="方法验证", task_type="test", status="waiting_external"),
        ])

        self.assertEqual("pending", calculate_project_status(project))

    def test_waiting_approval_does_not_start_project(self):
        project = Project(tasks=[
            Task(id=1, name="方案签批", task_type="approval_gate", status="waiting_approval"),
            Task(id=2, name="方法验证", task_type="test", status="scheduled"),
        ])

        self.assertEqual("pending", calculate_project_status(project))

    def test_actual_start_makes_scheduled_task_active(self):
        task = Task(id=1, name="方法开发", task_type="test", status="scheduled")
        task.time_slots = [TimeSlot(
            task_id=1,
            instrument_id=1,
            plan_start=datetime(2026, 7, 14, 8, 30),
            plan_end=datetime(2026, 7, 14, 12, 0),
            actual_start=datetime(2026, 7, 14, 8, 35),
        )]
        project = Project(tasks=[task])

        self.assertEqual("active", calculate_project_status(project))

    def test_blocked_before_start_remains_pending(self):
        project = Project(tasks=[
            Task(id=1, name="未开始但延期", task_type="test", status="blocked"),
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

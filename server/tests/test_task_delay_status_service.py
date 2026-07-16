import unittest

from app.models import Task
from app.services.task_delay_status_service import mark_task_delayed, reset_task_delay


class TaskDelayStatusServiceTest(unittest.TestCase):
    def test_mark_and_reset_persistent_delay_status(self):
        task = Task(status="scheduled", delay_status="not_delayed")

        mark_task_delayed(task)
        self.assertEqual("delayed", task.delay_status)

        reset_task_delay(task)
        self.assertEqual("not_delayed", task.delay_status)


if __name__ == "__main__":
    unittest.main()

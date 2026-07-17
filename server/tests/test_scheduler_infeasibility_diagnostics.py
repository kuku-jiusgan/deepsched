import unittest
from datetime import datetime
from types import SimpleNamespace

from app.services.scheduler_diagnostics import schedule_infeasibility_message


class SchedulerInfeasibilityDiagnosticsTest(unittest.TestCase):
    def test_reports_project_window_and_earliest_start_time(self):
        horizon_start = datetime(2026, 7, 17, 8, 30)
        project = SimpleNamespace(
            name="时间冲突项目",
            start_date=datetime(2026, 7, 10, 8, 30),
            end_date=datetime(2026, 7, 20, 1, 14),
        )
        task = SimpleNamespace(
            id=2,
            project_id=1,
            project=project,
            name="方案撰写",
            requires_instrument=False,
            est_duration_hours=2,
            switchover_hours=0,
        )
        zero_working_time = [0] * 200

        message = schedule_infeasibility_message(
            [task],
            [(task.id, 1)],
            {1: 25},
            {task.id: []},
            zero_working_time,
            {},
            horizon_start,
            199,
        )

        self.assertIn("项目【时间冲突项目】", message)
        self.assertIn("任务【方案撰写】", message)
        self.assertIn("项目时间：2026-07-10 08:30 至 2026-07-20 01:14", message)
        self.assertIn("最早可开始时间：2026-07-17 21:00", message)
        self.assertIn("任务需要约 2 小时，剩余有效工时约 0 小时", message)

    def test_fallback_lists_each_involved_project_with_time_and_hours(self):
        horizon_start = datetime(2026, 7, 17, 8, 30)
        first_project = SimpleNamespace(
            name="项目甲",
            start_date=datetime(2026, 7, 1, 8, 30),
            end_date=datetime(2026, 8, 1, 20, 0),
        )
        second_project = SimpleNamespace(
            name="项目乙",
            start_date=datetime(2026, 7, 2, 8, 30),
            end_date=datetime(2026, 9, 1, 20, 0),
        )
        tasks = [
            SimpleNamespace(
                id=1, project_id=1, project=first_project, name="任务甲",
                requires_instrument=True, est_duration_hours=22,
                switchover_hours=0,
            ),
            SimpleNamespace(
                id=2, project_id=2, project=second_project, name="任务乙",
                requires_instrument=True, est_duration_hours=56,
                switchover_hours=0,
            ),
        ]
        all_working_time = list(range(201))
        instruments = {
            task.id: [SimpleNamespace(id=task.id)]
            for task in tasks
        }

        message = schedule_infeasibility_message(
            tasks,
            [],
            {},
            instruments,
            all_working_time,
            {1: all_working_time, 2: all_working_time},
            horizon_start,
            200,
        )

        self.assertIn("【项目甲】", message)
        self.assertIn("待排总工时约 22 小时", message)
        self.assertIn("【项目乙】", message)
        self.assertIn("待排总工时约 56 小时", message)


if __name__ == "__main__":
    unittest.main()

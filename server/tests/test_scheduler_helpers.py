import unittest
from datetime import datetime

from app.services.scheduler_helpers import natural_day_boundary


class SchedulerHelpersTest(unittest.TestCase):
    def test_one_freeze_day_ends_at_today_midnight(self):
        now = datetime(2026, 7, 13, 13, 25, 40)

        boundary = natural_day_boundary(now, 1)

        self.assertEqual(datetime(2026, 7, 13, 23, 59, 59, 999999), boundary)

    def test_two_freeze_days_end_at_tomorrow_midnight(self):
        now = datetime(2026, 7, 13, 23, 50)

        boundary = natural_day_boundary(now, 2)

        self.assertEqual(datetime(2026, 7, 14, 23, 59, 59, 999999), boundary)

    def test_zero_freeze_days_uses_current_time(self):
        now = datetime(2026, 7, 13, 13, 25, 40)

        self.assertEqual(now, natural_day_boundary(now, 0))


if __name__ == "__main__":
    unittest.main()

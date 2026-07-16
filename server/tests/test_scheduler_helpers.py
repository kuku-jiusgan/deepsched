import unittest
from datetime import datetime

from app.services.scheduler_helpers import natural_day_boundary, to_units


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

    def test_fractional_hours_round_up_to_full_time_units(self):
        self.assertEqual(1, to_units(0.25))
        self.assertEqual(1, to_units(0.5))
        self.assertEqual(2, to_units(0.75))
        self.assertEqual(3, to_units(1.25))

if __name__ == "__main__":
    unittest.main()

from datetime import date

from django.test import SimpleTestCase

from todos.recurrence import next_due_date

# A fixed "today" (a Friday), so the tests give the same answer on any day.
TODAY = date(2026, 10, 9)


class NextDueDateTests(SimpleTestCase):
    def test_daily_next_day(self):
        self.assertEqual(
            next_due_date(date(2026, 10, 9), "daily", TODAY), date(2026, 10, 10)
        )

    def test_weekly_same_weekday(self):
        # Monday 12 Oct -> Monday 19 Oct.
        self.assertEqual(
            next_due_date(date(2026, 10, 12), "weekly", TODAY), date(2026, 10, 19)
        )

    def test_monthly_same_day(self):
        self.assertEqual(
            next_due_date(date(2026, 10, 15), "monthly", TODAY), date(2026, 11, 15)
        )

    def test_monthly_jan_31_to_feb_28(self):
        self.assertEqual(
            next_due_date(date(2027, 1, 31), "monthly", TODAY), date(2027, 2, 28)
        )

    def test_monthly_jan_31_to_feb_29_in_leap_year(self):
        self.assertEqual(
            next_due_date(date(2028, 1, 31), "monthly", TODAY), date(2028, 2, 29)
        )

    def test_monthly_feb_29_to_mar_29(self):
        self.assertEqual(
            next_due_date(date(2028, 2, 29), "monthly", TODAY), date(2028, 3, 29)
        )

    def test_monthly_mar_31_to_apr_30(self):
        self.assertEqual(
            next_due_date(date(2027, 3, 31), "monthly", TODAY), date(2027, 4, 30)
        )

    def test_monthly_dec_to_jan_next_year(self):
        self.assertEqual(
            next_due_date(date(2026, 12, 31), "monthly", TODAY), date(2027, 1, 31)
        )

    def test_done_early_moves_one_step(self):
        self.assertEqual(
            next_due_date(date(2026, 10, 20), "daily", TODAY), date(2026, 10, 21)
        )

    def test_overdue_daily_catches_up_to_tomorrow(self):
        # Not 9 Oct (today): the copy is always due after today.
        self.assertEqual(
            next_due_date(date(2026, 9, 30), "daily", TODAY), date(2026, 10, 10)
        )

    def test_overdue_weekly_catches_up_to_next_weekday(self):
        # Monday 14 Sep, today Friday 9 Oct -> Monday 12 Oct.
        self.assertEqual(
            next_due_date(date(2026, 9, 14), "weekly", TODAY), date(2026, 10, 12)
        )

    def test_overdue_weekly_never_lands_on_today(self):
        # Friday 2 Oct + 1 week is today, so it moves one more week.
        self.assertEqual(
            next_due_date(date(2026, 10, 2), "weekly", TODAY), date(2026, 10, 16)
        )

    def test_overdue_monthly_counts_from_original_day(self):
        # 31 Jan + 2 months is 31 Mar, not 28 Mar (31 Jan -> 28 Feb -> 28 Mar).
        self.assertEqual(
            next_due_date(date(2026, 1, 31), "monthly", date(2026, 3, 9)),
            date(2026, 3, 31),
        )

    def test_overdue_monthly_needs_one_more_month(self):
        # The first guess, 15 Mar, is before today (20 Mar).
        self.assertEqual(
            next_due_date(date(2026, 1, 15), "monthly", date(2026, 3, 20)),
            date(2026, 4, 15),
        )

    def test_overdue_monthly_never_lands_on_today(self):
        # The first guess, 9 Oct, is exactly today, so it moves one more month.
        self.assertEqual(
            next_due_date(date(2026, 8, 9), "monthly", TODAY), date(2026, 11, 9)
        )

    def test_very_old_due_date_is_fast(self):
        # A loop of one day at a time would take about 740,000 steps here.
        self.assertEqual(
            next_due_date(date(1, 1, 1), "daily", TODAY), date(2026, 10, 10)
        )

    def test_last_possible_date_returns_none(self):
        last = date(9999, 12, 31)
        for repeat in ["daily", "weekly", "monthly"]:
            with self.subTest(repeat=repeat):
                self.assertIsNone(next_due_date(last, repeat, TODAY))

    def test_never_raises(self):
        with self.assertRaises(ValueError):
            next_due_date(date(2026, 10, 9), "", TODAY)

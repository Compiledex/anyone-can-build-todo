"""The date math for repeating to-dos. No Django and no database.

`repeat` is a plain string, the same values as `Todo.Repeat`: "daily",
"weekly" or "monthly".
"""

import calendar
from datetime import timedelta

STEP_DAYS = {"daily": 1, "weekly": 7}


def add_months(day, months):
    """The same day of the month, `months` later.

    If that day does not exist (31 Jan + 1 month), it gives the last day of
    that month (28 or 29 Feb). Raises ValueError after the year 9999.
    """
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    # replace() raises ValueError for a year after 9999.
    return day.replace(year=year, month=month, day=min(day.day, last_day))


def next_due_date(due_date, repeat, today):
    """The first date after due_date, in steps of `repeat`, that is after today.

    Returns None if that date would be after 31 Dec 9999 (the last date Python can store).
    """
    if repeat not in STEP_DAYS and repeat != "monthly":
        raise ValueError(f"Not a repeat rule: {repeat!r}")
    # No loop: the number of steps is computed at once, so a due date in the
    # year 1 is as fast as one last week.
    try:
        if repeat in STEP_DAYS:
            step = STEP_DAYS[repeat]
            days = (today - due_date).days
            # `+ 1` takes the first step that is after today, never today.
            steps = max(1, days // step + 1)
            return due_date + timedelta(days=steps * step)
        months = (today.year - due_date.year) * 12 + (today.month - due_date.month)
        result = add_months(due_date, max(1, months))
        if result <= today:
            # The first guess is in today's month, so one more month is enough.
            result = add_months(due_date, max(1, months) + 1)
        return result
    except (OverflowError, ValueError):
        return None

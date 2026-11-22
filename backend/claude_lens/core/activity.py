"""Pure helpers for the Activity page: streaks over active local dates."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable

ONE_DAY = timedelta(days=1)


def streaks(active_days: Iterable[date], last_day: date) -> tuple[int, int]:
    """(current, longest) runs of consecutive active days.

    `last_day` is the end of the period (normally today, in the configured
    timezone). The current streak is the run that ends on `last_day`, or on the
    day before it: a streak isn't broken just because today has no activity
    *yet*. Days after `last_day` are ignored.
    """
    days = sorted({d for d in active_days if d <= last_day})
    if not days:
        return 0, 0

    longest = run = 1
    for prev, cur in zip(days, days[1:]):
        run = run + 1 if cur - prev == ONE_DAY else 1
        longest = max(longest, run)

    current = 0
    if days[-1] >= last_day - ONE_DAY:
        current = 1
        for prev, cur in zip(reversed(days[:-1]), reversed(days)):
            if cur - prev != ONE_DAY:
                break
            current += 1
    return current, longest

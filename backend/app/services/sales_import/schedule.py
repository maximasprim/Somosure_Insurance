"""When the next automatic import is due. Pure functions - no database - so the rules are easy to test.

Times are Nairobi time (UTC+3, no daylight saving), which is what staff think in; stored times are UTC.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

EAT = timezone(timedelta(hours=3))
FREQUENCIES = ("daily", "weekly", "monthly")
WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def next_run_after(now: datetime, *, frequency: str, weekday: int = 0, day_of_month: int = 1, hour: int = 6) -> datetime:
    """The first scheduled moment strictly after `now`, as a UTC time."""
    if frequency not in FREQUENCIES:
        raise ValueError(f"frequency must be one of {', '.join(FREQUENCIES)}")
    hour = min(max(int(hour), 0), 23)
    local = now.astimezone(EAT)
    slot = local.replace(hour=hour, minute=0, second=0, microsecond=0)

    if frequency == "daily":
        if slot <= local:
            slot += timedelta(days=1)
    elif frequency == "weekly":
        slot += timedelta(days=(min(max(int(weekday), 0), 6) - slot.weekday()) % 7)
        if slot <= local:
            slot += timedelta(days=7)
    else:  # monthly - capped at the 28th so every month has the day
        day = min(max(int(day_of_month), 1), 28)
        slot = slot.replace(day=day)
        if slot <= local:
            year, month = (slot.year + 1, 1) if slot.month == 12 else (slot.year, slot.month + 1)
            slot = slot.replace(year=year, month=month)
    return slot.astimezone(timezone.utc)


def describe(frequency: str, weekday: int, day_of_month: int, hour: int) -> str:
    """'Every Monday at 06:00 (Nairobi time)' - for the screen and for the run log."""
    at = f"{int(hour):02d}:00 (Nairobi time)"
    if frequency == "daily":
        return f"Every day at {at}"
    if frequency == "weekly":
        return f"Every {WEEKDAYS[min(max(int(weekday), 0), 6)]} at {at}"
    return f"On day {min(max(int(day_of_month), 1), 28)} of every month at {at}"

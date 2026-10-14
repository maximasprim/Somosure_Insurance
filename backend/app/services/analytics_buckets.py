"""Date bucketing for the analytics dashboard (app/services/analytics_service.py).

Pure Python on purpose - no database, no web framework - so it can be tested in
milliseconds. The dashboard shows a trend line over a chosen period; the period
decides how coarse the buckets are (days for a week or a month, weeks for a
quarter, months for a year) so a chart never has hundreds of points.
"""

from datetime import date, timedelta
from typing import Any

# The periods staff can pick, in days.
ALLOWED_RANGES = (7, 30, 90, 365)


def bucket_unit(days: int) -> str:
    """'day' up to a month, 'week' for a quarter, 'month' for a year."""
    if days <= 31:
        return "day"
    if days <= 100:
        return "week"
    return "month"


def floor_bucket(d: date, unit: str) -> date:
    """The first day of the bucket that `d` falls in (weeks start on Monday,
    matching Postgres' date_trunc('week', ...))."""
    if unit == "week":
        return d - timedelta(days=d.weekday())
    if unit == "month":
        return d.replace(day=1)
    return d


def _next_bucket(d: date, unit: str) -> date:
    if unit == "week":
        return d + timedelta(days=7)
    if unit == "month":
        return date(d.year + (d.month // 12), (d.month % 12) + 1, 1)
    return d + timedelta(days=1)


def bucket_dates(start: date, end: date, unit: str) -> list[date]:
    """Every bucket start from the one containing `start` up to the one
    containing `end`, so quiet periods show as zero instead of gaps."""
    out: list[date] = []
    current = floor_bucket(start, unit)
    last = floor_bucket(end, unit)
    while current <= last:
        out.append(current)
        current = _next_bucket(current, unit)
    return out


def merge_trend(dates: list[date], series: dict[str, dict[date, Any]]) -> list[dict]:
    """One row per bucket: {"date": "2026-10-14", "revenue": 0, "policies": 3, ...}.
    A bucket a series has no value for becomes 0."""
    rows = []
    for d in dates:
        row: dict[str, Any] = {"date": d.isoformat()}
        for name, values in series.items():
            row[name] = values.get(d, 0)
        rows.append(row)
    return rows


def pct_change(current: float, previous: float) -> float | None:
    """Percentage change from `previous` to `current`; None when there is nothing
    to compare against (previous is zero), so the screen shows "new" or nothing
    rather than an infinite or misleading number."""
    if not previous:
        return None
    return round((current - previous) / previous * 100, 1)

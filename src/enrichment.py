from datetime import date, datetime
from typing import Any


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(str(value).strip(), fmt).date()
        except ValueError:
            continue
    return None


def classify_status(days_left: int | None) -> str:
    if days_left is None:
        return "Unknown"
    if days_left < 0:
        return "Expired"
    if days_left <= 30:
        return "Expiring Soon"
    return "Active"


def policy_duration_years(start: date | None, end: date | None) -> int | None:
    if not start or not end or end < start:
        return None
    days = (end - start).days
    return max(1, round(days / 365))


def policy_type_from_duration(years: int | None) -> str | None:
    if years is None:
        return None
    return "Annual" if years == 1 else "Multi-Year"


def enrich(row: dict, *, today: date | None = None) -> dict:
    today = today or date.today()
    start = _parse_date(row.get("od_start_date"))
    end = _parse_date(row.get("od_end_date"))

    days_left = (end - today).days if end else None
    duration = policy_duration_years(start, end)

    return {
        **row,
        "od_start_date": start.isoformat() if start else row.get("od_start_date"),
        "od_end_date": end.isoformat() if end else row.get("od_end_date"),
        "days_left": days_left,
        "status": classify_status(days_left),
        "policy_duration": duration,
        "policy_type": policy_type_from_duration(duration),
    }

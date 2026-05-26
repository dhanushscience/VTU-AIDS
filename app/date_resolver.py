"""Resolve selected dates from calendar list or range + weekday skip."""

from __future__ import annotations

import datetime
from typing import Any


WEEKDAY_NAMES = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def _parse_iso(s: str) -> datetime.date:
    return datetime.date.fromisoformat(s.strip()[:10])


def _today() -> datetime.date:
    return datetime.date.today()


def _filter_not_future(dates: list[str]) -> list[str]:
    today = _today()
    return sorted(d for d in dates if _parse_iso(d) <= today)


def resolve_dates(payload: dict[str, Any]) -> list[str]:
    mode = payload.get("mode", "calendar")
    today = _today()

    if mode == "calendar":
        raw = payload.get("dates") or []
        dates = sorted({_parse_iso(d).isoformat() for d in raw if str(d).strip()})
        future = [d for d in dates if _parse_iso(d) > today]
        if future:
            raise ValueError(f"Future dates are not allowed: {', '.join(future[:3])}")
        return dates

    if mode == "range":
        start = _parse_iso(payload["from"])
        end = _parse_iso(payload["till"])
        if start > today:
            raise ValueError("'From' cannot be after today.")
        if end > today:
            end = today
        if end < start:
            raise ValueError("'till' must be on or after 'from'.")
        skip_weekdays = set(payload.get("skip_weekdays") or [])
        # skip_weekdays: list of "mon","sat",... — those weekdays are excluded
        skip_idx = set()
        for name in skip_weekdays:
            n = str(name).lower()[:3]
            if n in WEEKDAY_NAMES:
                skip_idx.add(WEEKDAY_NAMES.index(n))
        dates: list[str] = []
        cur = start
        while cur <= end:
            if cur.weekday() not in skip_idx:
                dates.append(cur.isoformat())
            cur += datetime.timedelta(days=1)
        return _filter_not_future(dates)

    raise ValueError(f"Unknown mode: {mode!r}")

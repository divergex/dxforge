import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any


class RuleError(ValueError):
    pass


def _parse_time(value: Any) -> time:
    if not isinstance(value, str):
        raise RuleError(f"invalid time: {value!r}")
    parts = value.split(":")
    if len(parts) != 2:
        raise RuleError(f"invalid time: {value!r}")
    try:
        return time(int(parts[0]), int(parts[1]))
    except ValueError:
        raise RuleError(f"invalid time: {value!r}")


def _parse_interval(value: Any) -> timedelta:
    if not isinstance(value, dict) or len(value) != 1:
        raise RuleError("'every' must be an object with exactly one unit")
    unit, amount = next(iter(value.items()))
    if not isinstance(amount, int) or amount <= 0:
        raise RuleError("'every' amount must be a positive integer")
    if unit == "minutes":
        return timedelta(minutes=amount)
    if unit == "hours":
        return timedelta(hours=amount)
    if unit == "days":
        return timedelta(days=amount)
    raise RuleError(f"unknown 'every' unit: {unit!r}")


def _parse_dates(value: Any) -> tuple[date, ...]:
    if not isinstance(value, list):
        raise RuleError("'dates' must be a list of ISO dates")
    dates: list[date] = []
    for raw in value:
        if not isinstance(raw, str):
            raise RuleError(f"invalid date: {raw!r}")
        try:
            dates.append(date.fromisoformat(raw))
        except ValueError:
            raise RuleError(f"invalid date: {raw!r}")
    return tuple(dates)


@dataclass(frozen=True)
class ScheduleRule:
    every: timedelta | None = None
    dates: tuple[date, ...] | None = None
    window: tuple[time, time] | None = None
    days: frozenset[int] | None = None
    at: time | None = None


def parse_rule(raw: str) -> ScheduleRule:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise RuleError("rule must be valid JSON")
    if not isinstance(data, dict):
        raise RuleError("rule must be a JSON object")

    has_every = "every" in data
    has_dates = "dates" in data
    if has_every == has_dates:
        raise RuleError("rule must have exactly one of 'every' or 'dates'")

    every = _parse_interval(data["every"]) if has_every else None
    dates = _parse_dates(data["dates"]) if has_dates else None
    window = None
    if "window" in data:
        w = data["window"]
        if not isinstance(w, dict) or set(w) != {"start", "end"}:
            raise RuleError("'window' must have 'start' and 'end'")
        start, end = _parse_time(w["start"]), _parse_time(w["end"])
        if end < start:
            raise RuleError("'window' end must not be before start")
        window = (start, end)
    days = None
    if "days" in data:
        raw_days = data["days"]
        if not isinstance(raw_days, list) or not all(
            isinstance(d, int) and 0 <= d <= 6 for d in raw_days
        ):
            raise RuleError("'days' must be a list of integers 0-6 (Monday=0)")
        days = frozenset(raw_days)
    at = _parse_time(data["at"]) if "at" in data else None
    return ScheduleRule(every=every, dates=dates, window=window, days=days, at=at)


def is_due(
    rule: ScheduleRule,
    now: datetime,
    last_fired: datetime | None = None,
) -> bool:
    if rule.dates is not None:
        if now.date() not in rule.dates:
            return False
        if rule.at is not None and now.time() < rule.at:
            return False
        return last_fired is None or last_fired.date() < now.date()
    if rule.window is not None and not (rule.window[0] <= now.time() <= rule.window[1]):
        return False
    if rule.days is not None and now.weekday() not in rule.days:
        return False
    interval = rule.every
    if interval is None:
        return False
    if interval >= timedelta(days=1) and rule.at is not None and now.time() < rule.at:
        return False
    if last_fired is None:
        return True
    return (now - last_fired) >= interval


UTC = timezone.utc


def utcnow() -> datetime:
    return datetime.now(UTC)

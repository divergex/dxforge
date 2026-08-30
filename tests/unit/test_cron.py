from datetime import datetime, timedelta, timezone

import pytest

from dxforge.scheduler.cron import RuleError, is_due, parse_rule

TZ = timezone.utc


def _now(**kwargs: int) -> datetime:
    return datetime(2026, 9, 1, 10, 0, 0, tzinfo=TZ) + timedelta(**kwargs)


def test_parse_every_interval() -> None:
    rule = parse_rule('{"every": {"minutes": 30}}')
    assert rule.every == timedelta(minutes=30)


def test_parse_rejects_missing_or_double_source() -> None:
    with pytest.raises(RuleError):
        _ = parse_rule("{}")
    with pytest.raises(RuleError):
        _ = parse_rule('{"every": {"hours": 1}, "dates": ["2026-09-01"]}')


def test_parse_rejects_bad_interval() -> None:
    with pytest.raises(RuleError):
        _ = parse_rule('{"every": {"fortnights": 1}}')
    with pytest.raises(RuleError):
        _ = parse_rule('{"every": {"minutes": -1}}')
    with pytest.raises(RuleError):
        _ = parse_rule('{"every": {"hours": 1, "minutes": 2}}')


def test_parse_rejects_bad_dates_and_window() -> None:
    with pytest.raises(RuleError):
        _ = parse_rule('{"dates": ["not-a-date"]}')
    with pytest.raises(RuleError):
        _ = parse_rule('{"every": {"days": 1}, "window": {"start": "18:00", "end": "09:00"}}')


def test_every_due_after_interval() -> None:
    rule = parse_rule('{"every": {"minutes": 30}}')
    assert is_due(rule, _now())
    assert not is_due(rule, _now(), last_fired=_now(minutes=-10))
    assert is_due(rule, _now(), last_fired=_now(minutes=-31))


def test_window_restricts_firing() -> None:
    rule = parse_rule('{"every": {"hours": 1}, "window": {"start": "09:00", "end": "17:00"}}')
    assert is_due(rule, _now())  # 10:00, inside window
    assert not is_due(rule, _now(hours=10))  # 20:00, outside window


def test_days_filter() -> None:
    # 2026-09-01 is a Tuesday (weekday 1); Monday = 0.
    rule = parse_rule('{"every": {"days": 1}, "days": [0]}')
    assert not is_due(rule, _now())  # Tuesday: outside the Monday-only window
    # Tuesday stays not due even after the interval elapsed since last fire (Monday).
    assert not is_due(rule, _now(), last_fired=_now(days=-1))
    # Next Monday (2026-09-07) the interval has elapsed and the day matches.
    assert is_due(rule, _now(days=6), last_fired=_now(days=-1))


def test_at_defers_firing_until_time() -> None:
    rule = parse_rule('{"every": {"days": 1}, "at": "11:00"}')
    assert not is_due(rule, _now())  # 10:00 < 11:00
    assert is_due(rule, _now(hours=2))  # 12:00 >= 11:00


def test_dates_list_fires_once_per_date() -> None:
    rule = parse_rule('{"dates": ["2026-09-01", "2026-09-05"]}')
    assert is_due(rule, _now())
    assert not is_due(rule, _now(), last_fired=_now())
    assert not is_due(rule, _now(days=1))  # 2026-09-02 not in list
    assert is_due(rule, _now(days=4))  # 2026-09-05


def test_dates_list_with_at_defers_until_time() -> None:
    rule = parse_rule('{"dates": ["2026-09-01"], "at": "11:00"}')
    assert not is_due(rule, _now())  # 10:00 < 11:00 on the listed date
    assert is_due(rule, _now(hours=2))  # 12:00 >= 11:00 on the listed date
    assert not is_due(rule, _now(hours=2), last_fired=_now(hours=2))  # already fired today


def test_invalid_json_rejected() -> None:
    with pytest.raises(RuleError):
        _ = parse_rule("not json")

from datetime import datetime, timedelta, timezone

from dxforge.db.models import Schedule
from dxforge.scheduler.cron import parse_rule
from dxforge.scheduler.dispatcher import schedule_is_due

NOW = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


def _schedule(
    trigger_at: datetime | None = None, last_fired_at: datetime | None = None
) -> Schedule:
    return Schedule(trigger_at=trigger_at, last_fired_at=last_fired_at)


def test_pending_trigger_fires_without_any_rule() -> None:
    assert schedule_is_due(_schedule(trigger_at=NOW - timedelta(seconds=1)), None, NOW)


def test_consumed_run_once_schedule_never_fires_again() -> None:
    schedule = _schedule(trigger_at=None, last_fired_at=NOW - timedelta(days=365))
    assert not schedule_is_due(schedule, None, NOW)


def test_pending_trigger_beats_rule_restrictions() -> None:
    rule = parse_rule('{"every": {"days": 1}, "days": [0]}')  # Mondays only; NOW is a Tuesday
    assert not schedule_is_due(_schedule(last_fired_at=NOW - timedelta(days=2)), rule, NOW)
    assert schedule_is_due(_schedule(trigger_at=NOW, last_fired_at=NOW - timedelta(days=2)), rule, NOW)


def test_cycle_takes_over_after_the_first_firing() -> None:
    rule = parse_rule('{"every": {"hours": 1}}')
    assert not schedule_is_due(_schedule(last_fired_at=NOW - timedelta(minutes=10)), rule, NOW)
    assert schedule_is_due(_schedule(last_fired_at=NOW - timedelta(minutes=61)), rule, NOW)

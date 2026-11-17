"""Decide what is due and hand it to detached supervisors; never run code itself.

Dispatching only records an Execution and spawns `executor.supervisor` in its own
session, so a long-running process never blocks a dispatch cycle and survives this
worker (and the API) stopping. `reconcile_executions` re-adopts or closes the
executions left behind by a previous worker run.
"""

import logging
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

import psycopg
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from dxforge.config import settings
from dxforge.db.models import Execution, Function, Schedule, Tenant, Version
from dxforge.db.session import engine, session_factory
from dxforge.executor import run_dir
from dxforge.scheduler import wakeup
from dxforge.scheduler.cron import ScheduleRule, is_due, parse_rule, utcnow

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SUPERVISOR_MODULE = "dxforge.executor.supervisor"

# Supervisors we spawned; polled so finished ones do not linger as zombies.
_children: list["subprocess.Popen[bytes]"] = []


def _tenant_ids() -> list[uuid.UUID]:
    with Session(bind=engine) as lookup:
        return list(lookup.execute(select(Tenant.id)).scalars().all())


def schedule_is_due(schedule: Schedule, rule: ScheduleRule | None, now: datetime) -> bool:
    """A pending trigger_at fires once; afterwards only the repeat rule (if any) does."""
    if schedule.trigger_at is not None:
        return schedule.trigger_at <= now
    return rule is not None and is_due(rule, now, schedule.last_fired_at)


def _claim_if_due(
    session: Session, tenant_id: uuid.UUID, schedule: Schedule, now: datetime
) -> uuid.UUID | None:
    """Atomically consume the schedule's firing and record its Execution.

    The compare-and-set on (trigger_at, last_fired_at) makes concurrent dispatchers
    (worker poll and wakeup) fire a given occurrence exactly once.
    """
    try:
        rule = parse_rule(schedule.rule) if schedule.rule is not None else None
    except ValueError:
        logger.warning("schedule %s has invalid rule", schedule.id)
        return None
    if not schedule_is_due(schedule, rule, now):
        return None
    function = session.get(Function, schedule.function_id)
    if function is None:
        return None
    version = session.get(Version, schedule.version_id or function.version_id)
    if version is None or version.project_id != function.project_id:
        logger.warning(
            "schedule %s references version outside its function's project", schedule.id
        )
        return None

    claimed = session.execute(
        update(Schedule)
        .where(
            Schedule.id == schedule.id,
            Schedule.trigger_at.is_not_distinct_from(schedule.trigger_at),
            Schedule.last_fired_at.is_not_distinct_from(schedule.last_fired_at),
        )
        .values(trigger_at=None, last_fired_at=now)
        .returning(Schedule.id)
        .execution_options(synchronize_session=False)
    ).scalar_one_or_none()
    if claimed is None:
        session.rollback()
        return None

    execution = Execution(
        tenant_id=tenant_id,
        schedule_id=schedule.id,
        function_id=function.id,
        version_id=version.id,
        status="running",
        executor_backend=schedule.executor_backend,
        heartbeat_at=now,
    )
    session.add(execution)
    session.commit()
    return execution.id


def _spawn_supervisor(tenant_id: uuid.UUID, execution_id: uuid.UUID) -> int:
    directory = run_dir.create(execution_id)
    with (directory / "supervisor.log").open("wb") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", _SUPERVISOR_MODULE, str(tenant_id), str(execution_id)],
            cwd=_REPO_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=log,
            start_new_session=True,
        )
    _children.append(process)
    return process.pid


def start_execution(tenant_id: uuid.UUID, execution_id: uuid.UUID) -> None:
    """Spawn the detached supervisor for a recorded execution and note its pid."""
    session = session_factory(tenant_id)
    try:
        try:
            pid = _spawn_supervisor(tenant_id, execution_id)
        except OSError as exc:
            logger.exception("cannot spawn supervisor for execution %s", execution_id)
            _ = session.execute(
                update(Execution)
                .where(Execution.id == execution_id)
                .values(
                    status="failed",
                    stderr=f"cannot start supervisor: {exc}",
                    finished_at=utcnow(),
                )
            )
        else:
            _ = session.execute(
                update(Execution).where(Execution.id == execution_id).values(supervisor_pid=pid)
            )
        session.commit()
    finally:
        session.close()


def dispatch_cycle(now: datetime | None = None) -> list[uuid.UUID]:
    """Start an execution for every due schedule; returns their ids without waiting."""
    now = now or utcnow()
    _children[:] = [child for child in _children if child.poll() is None]
    created: list[tuple[uuid.UUID, uuid.UUID]] = []
    for tenant_id in _tenant_ids():
        session = session_factory(tenant_id)
        try:
            for schedule in session.execute(
                select(Schedule).where(Schedule.enabled)
            ).scalars().all():
                execution_id = _claim_if_due(session, tenant_id, schedule, now)
                if execution_id is not None:
                    created.append((tenant_id, execution_id))
        finally:
            session.close()
    for owner_tenant_id, execution_id in created:
        start_execution(owner_tenant_id, execution_id)
    return [execution_id for _, execution_id in created]


def dispatch_schedule(
    tenant_id: uuid.UUID, schedule_id: uuid.UUID, now: datetime | None = None
) -> uuid.UUID | None:
    """Start one schedule if it is due (used when it was just submitted)."""
    now = now or utcnow()
    session = session_factory(tenant_id)
    try:
        schedule = session.get(Schedule, schedule_id)
        if schedule is None or not schedule.enabled:
            return None
        execution_id = _claim_if_due(session, tenant_id, schedule, now)
    finally:
        session.close()
    if execution_id is not None:
        start_execution(tenant_id, execution_id)
    return execution_id


def _supervisor_alive(pid: int | None, execution_id: uuid.UUID) -> bool:
    """Linux: the pid must still be *this* execution's supervisor (guards pid reuse;
    zombies have an empty cmdline)."""
    if pid is None:
        return False
    try:
        cmdline = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return False
    return _SUPERVISOR_MODULE.encode() in cmdline and str(execution_id).encode() in cmdline


def reconcile_executions(now: datetime | None = None) -> list[uuid.UUID]:
    """Close executions whose supervisor vanished (crash, reboot); returns their ids.

    Executions whose supervisor is alive, or heartbeated recently, are left running:
    that is how processes started before a dxforge restart are recovered.
    """
    now = now or utcnow()
    lost: list[uuid.UUID] = []
    for tenant_id in _tenant_ids():
        session = session_factory(tenant_id)
        try:
            running = session.execute(
                select(Execution).where(Execution.status == "running")
            ).scalars().all()
            for execution in running:
                last_seen = execution.heartbeat_at or execution.started_at
                if (now - last_seen).total_seconds() < settings.supervisor_stale_seconds:
                    continue
                if _supervisor_alive(execution.supervisor_pid, execution.id):
                    continue
                stdout, stderr = run_dir.read_logs(execution.id)
                execution.stdout = stdout
                execution.stderr = stderr + "\nsupervisor process vanished; result unknown\n"
                execution.status = "lost"
                execution.finished_at = now
                execution.duration_seconds = (now - execution.started_at).total_seconds()
                session.commit()
                run_dir.remove(execution.id)
                lost.append(execution.id)
        finally:
            session.close()
    return lost


def _dispatch_notified(payload: str) -> None:
    ids = wakeup.parse(payload)
    if ids is None:
        logger.warning("ignoring malformed dispatch notification %r", payload)
        return
    _ = dispatch_schedule(*ids)


def _cycle() -> None:
    try:
        _ = reconcile_executions()
        _ = dispatch_cycle()
    except Exception:
        logger.exception("dispatch cycle failed")


def _open_listener() -> wakeup.Listener | None:
    try:
        return wakeup.Listener()
    except Exception:
        logger.exception("cannot listen for schedule wakeups; polling only")
        return None


def run_forever(interval_seconds: float = 30.0) -> None:
    """Poll every interval_seconds; a submitted schedule wakes the loop immediately."""
    listener = _open_listener()
    next_cycle = 0.0
    while True:
        if time.monotonic() >= next_cycle:
            _cycle()
            next_cycle = time.monotonic() + interval_seconds
        remaining = max(next_cycle - time.monotonic(), 0.0)
        if listener is None:
            time.sleep(remaining)
            listener = _open_listener()
            continue
        try:
            payloads = listener.wait(remaining)
        except psycopg.Error:
            logger.exception("wakeup listener lost; reconnecting")
            listener.close()
            listener = _open_listener()
            continue
        for payload in payloads:
            try:
                _dispatch_notified(payload)
            except Exception:
                logger.exception("wakeup dispatch failed for %r", payload)

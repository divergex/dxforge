import logging
import shutil
import time
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from dxforge.config import settings
from dxforge.db.models import Execution, Function, Schedule, Tenant, Version
from dxforge.db.session import engine, session_factory
from dxforge.executor import EXECUTORS
from dxforge.executor.base import Executor
from dxforge.executor.sandbox import fetch_decrypt_to_file
from dxforge.scheduler.cron import is_due, parse_rule, utcnow

logger = logging.getLogger(__name__)


def _resolve_executor(tenant_id: uuid.UUID, requested: str) -> Executor:
    """Single decision point for executor selection.

    Per-tenant backend permissions (e.g. host allowed only for some tenants)
    will be checked here against the tenant's policy.
    """
    executor = EXECUTORS.get(requested)
    if executor is None:
        logger.warning(
            "tenant %s schedule requests unknown executor %r; falling back to docker",
            tenant_id,
            requested,
        )
        return EXECUTORS["docker"]
    return executor


def _truncate(text: str) -> str:
    return text[: settings.log_max_bytes]


def execute_execution(tenant_id: uuid.UUID, execution_id: uuid.UUID) -> None:
    session = session_factory(tenant_id)
    artifact = None
    try:
        execution = session.get(Execution, execution_id)
        if execution is None:
            return
        version = session.get(Version, execution.version_id)
        function = session.get(Function, execution.function_id)
        if version is None or function is None:
            execution.status = "failed"
            session.commit()
            return
        executor = _resolve_executor(tenant_id, execution.executor_backend)
        artifact = fetch_decrypt_to_file(version)
        result = executor.run(
            artifact, version, function.command, settings.execution_timeout_seconds
        )
        execution.exit_code = result.exit_code
        if result.exit_code == 124:
            execution.status = "timeout"
        else:
            execution.status = "success" if result.exit_code == 0 else "failed"
        execution.stdout = _truncate(result.stdout)
        execution.stderr = _truncate(result.stderr)
        execution.finished_at = datetime.now(tz=utcnow().tzinfo)
        execution.duration_seconds = result.duration_seconds
        session.commit()
    except Exception:
        logger.exception("execution %s failed unexpectedly", execution_id)
        if session.in_transaction():
            session.rollback()
        execution = session.get(Execution, execution_id)
        if execution is not None:
            execution.status = "failed"
            execution.finished_at = datetime.now(tz=utcnow().tzinfo)
            session.commit()
    finally:
        session.close()
        if artifact is not None:
            shutil.rmtree(artifact.parent, ignore_errors=True)


def dispatch_cycle(now: datetime | None = None) -> list[uuid.UUID]:
    """Create and run executions for every due schedule; returns execution ids."""
    now = now or utcnow()
    created: list[tuple[uuid.UUID, uuid.UUID]] = []
    with Session(bind=engine) as lookup:
        tenant_ids = list(lookup.execute(select(Tenant.id)).scalars().all())
    for tenant_id in tenant_ids:
        session = session_factory(tenant_id)
        try:
            schedules = session.execute(
                select(Schedule).where(Schedule.enabled)
            ).scalars().all()
            for schedule in schedules:
                try:
                    rule = parse_rule(schedule.rule)
                except ValueError:
                    logger.warning("schedule %s has invalid rule", schedule.id)
                    continue
                if not is_due(rule, now, schedule.last_fired_at):
                    continue
                function = session.get(Function, schedule.function_id)
                if function is None:
                    continue
                version = session.get(Version, schedule.version_id or function.version_id)
                if version is None or version.project_id != function.project_id:
                    logger.warning(
                        "schedule %s references version outside its function's project",
                        schedule.id,
                    )
                    continue
                execution = Execution(
                    tenant_id=tenant_id,
                    schedule_id=schedule.id,
                    function_id=function.id,
                    version_id=version.id,
                    status="running",
                    executor_backend=schedule.executor_backend,
                )
                session.add(execution)
                schedule.last_fired_at = now
                session.commit()
                session.refresh(execution)
                created.append((tenant_id, execution.id))
        finally:
            session.close()
    for owner_tenant_id, execution_id in created:
        execute_execution(owner_tenant_id, execution_id)
    return [execution_id for _, execution_id in created]


def run_forever(interval_seconds: float = 30.0) -> None:
    while True:
        _ = dispatch_cycle()
        time.sleep(interval_seconds)

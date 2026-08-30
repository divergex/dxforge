from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from dxforge.api.schemas import ScheduleCreate, ScheduleOut
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.db.models import Function, Schedule, Version
from dxforge.executor import EXECUTORS
from dxforge.scheduler.cron import parse_rule

router = APIRouter(prefix="/schedules", tags=["schedules"])


def _owned(context: TenantContext, schedule_id: UUID) -> Schedule:
    schedule = context.session.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="schedule not found")
    return schedule


def _validate_target(context: TenantContext, body: ScheduleCreate) -> None:
    if body.executor_backend not in EXECUTORS:
        raise HTTPException(
            status_code=422,
            detail=f"unknown executor backend: {body.executor_backend!r}",
        )
    function = context.session.get(Function, body.function_id)
    if function is None:
        raise HTTPException(status_code=404, detail="function not found")
    if body.version_id is not None:
        version = context.session.get(Version, body.version_id)
        if version is None or version.project_id != function.project_id:
            raise HTTPException(status_code=400, detail="version does not belong to function")
    try:
        _ = parse_rule(body.rule)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("", status_code=201, response_model=ScheduleOut)
def create_schedule(
    body: ScheduleCreate,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Schedule:
    _validate_target(context, body)
    schedule = Schedule(
        tenant_id=context.tenant.id,
        function_id=body.function_id,
        version_id=body.version_id,
        rule=body.rule,
        enabled=body.enabled,
        executor_backend=body.executor_backend,
    )
    context.session.add(schedule)
    context.session.commit()
    context.session.refresh(schedule)
    return schedule


@router.get("", response_model=list[ScheduleOut])
def list_schedules(
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> list[Schedule]:
    return list(
        context.session.execute(select(Schedule).order_by(Schedule.created_at)).scalars().all()
    )


@router.get("/{schedule_id}", response_model=ScheduleOut)
def get_schedule(
    schedule_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Schedule:
    return _owned(context, schedule_id)


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule(
    schedule_id: UUID,
    body: ScheduleCreate,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Schedule:
    schedule = _owned(context, schedule_id)
    _validate_target(context, body)
    schedule.function_id = body.function_id
    schedule.version_id = body.version_id
    schedule.rule = body.rule
    schedule.enabled = body.enabled
    schedule.executor_backend = body.executor_backend
    context.session.commit()
    context.session.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=204)
def delete_schedule(
    schedule_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Response:
    schedule = _owned(context, schedule_id)
    context.session.delete(schedule)
    context.session.commit()
    return Response(status_code=204)

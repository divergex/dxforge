from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from dxforge.api.schemas import ExecutionLogsOut, ExecutionOut
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.db.models import Execution
from dxforge.executor import run_dir

router = APIRouter(prefix="/executions", tags=["executions"])


def _owned(context: TenantContext, execution_id: UUID) -> Execution:
    execution = context.session.get(Execution, execution_id)
    if execution is None:
        raise HTTPException(status_code=404, detail="execution not found")
    return execution


@router.get("", response_model=list[ExecutionOut])
def list_executions(
    context: Annotated[TenantContext, Depends(get_current_tenant)],
    schedule_id: UUID | None = None,
    function_id: UUID | None = None,
) -> list[Execution]:
    statement = select(Execution).order_by(Execution.started_at.desc())
    if schedule_id is not None:
        statement = statement.where(Execution.schedule_id == schedule_id)
    if function_id is not None:
        statement = statement.where(Execution.function_id == function_id)
    return list(context.session.execute(statement).scalars().all())


@router.get("/{execution_id}", response_model=ExecutionOut)
def get_execution(
    execution_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Execution:
    return _owned(context, execution_id)


@router.get("/{execution_id}/logs", response_model=ExecutionLogsOut)
def execution_logs(
    execution_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> ExecutionLogsOut:
    execution = _owned(context, execution_id)
    if execution.status == "running":
        stdout, stderr = run_dir.read_logs(execution.id)
        return ExecutionLogsOut(execution_id=execution.id, stdout=stdout, stderr=stderr)
    return ExecutionLogsOut(
        execution_id=execution.id, stdout=execution.stdout, stderr=execution.stderr
    )


@router.post("/{execution_id}/stop", status_code=202, response_model=ExecutionOut)
def stop_execution(
    execution_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Execution:
    """Ask the supervisor to terminate the process; it reports `stopped` shortly after."""
    execution = _owned(context, execution_id)
    if execution.status != "running":
        raise HTTPException(status_code=409, detail="execution is not running")
    execution.stop_requested = True
    context.session.commit()
    context.session.refresh(execution)
    return execution

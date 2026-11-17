from typing import Annotated
from urllib.parse import urlsplit
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from dxforge.api.schemas import FunctionCreate, FunctionOut, VersionOut
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.db.models import Function, Project, Version

router = APIRouter(prefix="/functions", tags=["functions"])


def _owned(context: TenantContext, function_id: UUID) -> Function:
    function = context.session.get(Function, function_id)
    if function is None:
        raise HTTPException(status_code=404, detail="function not found")
    return function


def _validate_command(command: list[str]) -> None:
    if not command or len(command) > 64:
        raise HTTPException(status_code=422, detail="command must be 1-64 arguments")
    if sum(len(arg) for arg in command) > 4096:
        raise HTTPException(status_code=422, detail="command too long")
    if any(not arg or "\x00" in arg for arg in command):
        raise HTTPException(status_code=422, detail="command arguments must be non-empty")


_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def _validate_health_url(health_url: str | None) -> None:
    """Probes run on the dxforge host, so only loopback targets are allowed."""
    if health_url is None:
        return
    try:
        parsed = urlsplit(health_url)
        _ = parsed.port
    except ValueError:
        raise HTTPException(status_code=422, detail="health_url is not a valid URL")
    if parsed.scheme not in ("http", "https") or parsed.hostname not in _LOOPBACK_HOSTS:
        raise HTTPException(
            status_code=422,
            detail="health_url must be an http(s) URL on localhost, 127.0.0.1 or ::1",
        )


def _pinned_version(context: TenantContext, body: FunctionCreate) -> Version:
    if context.session.get(Project, body.project_id) is None:
        raise HTTPException(status_code=404, detail="project not found")
    version = context.session.get(Version, body.version_id)
    if version is None or version.project_id != body.project_id:
        raise HTTPException(status_code=400, detail="version does not belong to project")
    return version


@router.post("", status_code=201, response_model=FunctionOut)
def create_function(
    body: FunctionCreate,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Function:
    _pinned_version(context, body)
    _validate_command(body.command)
    _validate_health_url(body.health_url)
    function = Function(
        tenant_id=context.tenant.id,
        project_id=body.project_id,
        version_id=body.version_id,
        name=body.name,
        description=body.description,
        command=body.command,
        health_url=body.health_url,
        alive_timeout_seconds=body.alive_timeout_seconds,
        hard_timeout_seconds=body.hard_timeout_seconds,
    )
    context.session.add(function)
    context.session.commit()
    context.session.refresh(function)
    return function


@router.get("", response_model=list[FunctionOut])
def list_functions(
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> list[Function]:
    return list(
        context.session.execute(select(Function).order_by(Function.created_at)).scalars().all()
    )


@router.get("/{function_id}", response_model=FunctionOut)
def get_function(
    function_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Function:
    return _owned(context, function_id)


@router.put("/{function_id}", response_model=FunctionOut)
def update_function(
    function_id: UUID,
    body: FunctionCreate,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Function:
    function = _owned(context, function_id)
    _pinned_version(context, body)
    _validate_command(body.command)
    _validate_health_url(body.health_url)
    function.project_id = body.project_id
    function.version_id = body.version_id
    function.name = body.name
    function.description = body.description
    function.command = body.command
    function.health_url = body.health_url
    function.alive_timeout_seconds = body.alive_timeout_seconds
    function.hard_timeout_seconds = body.hard_timeout_seconds
    context.session.commit()
    context.session.refresh(function)
    return function


@router.delete("/{function_id}", status_code=204)
def delete_function(
    function_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Response:
    function = _owned(context, function_id)
    context.session.delete(function)
    context.session.commit()
    return Response(status_code=204)


@router.get("/{function_id}/versions", response_model=list[VersionOut])
def list_function_versions(
    function_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> list[Version]:
    function = _owned(context, function_id)
    return list(
        context.session.execute(
            select(Version)
            .where(Version.project_id == function.project_id)
            .order_by(Version.version_number.desc())
        ).scalars().all()
    )

from typing import Annotated
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
    function = Function(
        tenant_id=context.tenant.id,
        project_id=body.project_id,
        version_id=body.version_id,
        name=body.name,
        description=body.description,
        handler=body.handler,
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
    function.project_id = body.project_id
    function.version_id = body.version_id
    function.name = body.name
    function.description = body.description
    function.handler = body.handler
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

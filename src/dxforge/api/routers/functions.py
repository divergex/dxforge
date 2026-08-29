from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select

from dxforge.api.schemas import FunctionCreate, FunctionOut
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.db.models import Function

router = APIRouter(prefix="/functions", tags=["functions"])


def _owned(context: TenantContext, function_id: UUID) -> Function:
    function = context.session.get(Function, function_id)
    if function is None:
        raise HTTPException(status_code=404, detail="function not found")
    return function


@router.post("", status_code=201, response_model=FunctionOut)
def create_function(
    body: FunctionCreate,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> Function:
    function = Function(
        tenant_id=context.tenant.id,
        name=body.name,
        description=body.description,
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
    function.name = body.name
    function.description = body.description
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

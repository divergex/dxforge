from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from dxforge.api.schemas import VersionOut
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.db.models import Function, Version

router = APIRouter(prefix="/functions/{function_id}/versions", tags=["versions"])


@router.get("", response_model=list[VersionOut])
def list_versions(
    function_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> list[Version]:
    if context.session.get(Function, function_id) is None:
        raise HTTPException(status_code=404, detail="function not found")
    return list(
        context.session.execute(
            select(Version)
            .where(Version.function_id == function_id)
            .order_by(Version.version_number.desc())
        ).scalars().all()
    )

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from dxforge.api.schemas import TenantCreate, TenantCreated
from dxforge.auth.api_keys import generate_key, hash_key, rotate_api_key
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.db.models import Tenant
from dxforge.db.session import engine

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", status_code=201, response_model=TenantCreated)
def register_tenant(body: TenantCreate) -> TenantCreated:
    api_key = generate_key()
    tenant = Tenant(name=body.name, api_key_hash=hash_key(api_key))
    with Session(bind=engine) as session:
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
    return TenantCreated(id=tenant.id, name=tenant.name, api_key=api_key)


@router.post("/{tenant_id}/rotate-key", response_model=TenantCreated)
def rotate_key(
    tenant_id: UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> TenantCreated:
    if context.tenant.id != tenant_id:
        raise HTTPException(status_code=404, detail="tenant not found")
    tenant = context.session.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="tenant not found")
    new_key = rotate_api_key(tenant, context.session)
    return TenantCreated(id=tenant.id, name=tenant.name, api_key=new_key)

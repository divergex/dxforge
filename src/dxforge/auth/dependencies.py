from collections.abc import Generator
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from dxforge.auth.api_keys import hash_key
from dxforge.db.models import Tenant
from dxforge.db.session import engine, session_factory


@dataclass
class TenantContext:
    tenant: Tenant
    session: Session


def get_current_tenant(
    authorization: Annotated[str | None, Header()] = None,
) -> Generator[TenantContext, None, None]:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="missing or malformed Authorization header"
        )
    key = authorization.removeprefix("Bearer ").strip()
    if not key:
        raise HTTPException(
            status_code=401, detail="missing or malformed Authorization header"
        )
    with Session(bind=engine) as lookup:
        tenant = lookup.execute(
            select(Tenant).where(Tenant.api_key_hash == hash_key(key))
        ).scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    session = session_factory(tenant.id)
    try:
        yield TenantContext(tenant=tenant, session=session)
    finally:
        session.close()

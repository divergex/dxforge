from typing import Annotated

from fastapi import APIRouter, Depends

from dxforge.api.schemas import CredentialCreate, CredentialOut
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.crypto.envelope import encrypt_bytes
from dxforge.crypto.kms_client import build_credential_client, key_version_from_wrapped
from dxforge.db.models import GitCredential

router = APIRouter(prefix="/credentials", tags=["credentials"])


@router.post("", status_code=201, response_model=CredentialOut)
def create_credential(
    body: CredentialCreate,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> CredentialOut:
    dek, wrapped = build_credential_client().generate_data_key()
    try:
        ciphertext = encrypt_bytes(dek, body.private_key.encode())
    finally:
        dek.wipe()
    credential = GitCredential(
        tenant_id=context.tenant.id,
        name=body.name,
        wrapped_dek=wrapped,
        key_version=key_version_from_wrapped(wrapped),
        ciphertext=ciphertext,
    )
    context.session.add(credential)
    context.session.commit()
    context.session.refresh(credential)
    return CredentialOut(id=credential.id, name=credential.name)

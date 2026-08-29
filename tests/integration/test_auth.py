import uuid
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from dxforge.auth.api_keys import generate_key, hash_key, rotate_api_key
from dxforge.auth.dependencies import TenantContext, get_current_tenant
from dxforge.db.models import Tenant
from dxforge.db.session import engine

app = FastAPI()


@app.get("/whoami")
def whoami(context: Annotated[TenantContext, Depends(get_current_tenant)]) -> dict[str, str]:
    return {"tenant_id": str(context.tenant.id)}


@app.get("/functions-count")
def functions_count(
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict[str, int]:
    count = context.session.execute(text("SELECT count(*) FROM functions")).scalar_one()
    return {"count": count}


@app.get("/function/{function_id}")
def function_exists(
    function_id: uuid.UUID,
    context: Annotated[TenantContext, Depends(get_current_tenant)],
) -> dict[str, bool]:
    row = context.session.execute(
        text("SELECT name FROM functions WHERE id = :id"), {"id": function_id}
    ).first()
    return {"found": row is not None}


client = TestClient(app)


def _register_tenant(name: str = "t") -> tuple[uuid.UUID, str]:
    key = generate_key()
    with engine.begin() as conn:
        tenant_id = conn.execute(
            text(
                "INSERT INTO tenants (id, name, api_key_hash) VALUES (:id, :name, :hash) RETURNING id"
            ),
            {"id": uuid.uuid4(), "name": name, "hash": hash_key(key)},
        ).scalar_one()
    return tenant_id, key


def _auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def test_missing_key_is_401() -> None:
    assert client.get("/whoami").status_code == 401


def test_malformed_header_is_401() -> None:
    response = client.get("/whoami", headers={"Authorization": "Basic abc"})
    assert response.status_code == 401


def test_garbage_key_is_401() -> None:
    response = client.get("/whoami", headers=_auth("not-a-real-key"))
    assert response.status_code == 401


def test_valid_key_resolves_tenant() -> None:
    tenant_id, key = _register_tenant()
    response = client.get("/whoami", headers=_auth(key))
    assert response.status_code == 200
    assert response.json()["tenant_id"] == str(tenant_id)


def test_rotated_key_invalidates_old_one() -> None:
    tenant_id, key = _register_tenant()
    with Session(bind=engine) as session:
        tenant = session.get(Tenant, tenant_id)
        assert tenant is not None
        new_key = rotate_api_key(tenant, session)
    assert client.get("/whoami", headers=_auth(key)).status_code == 401
    assert client.get("/whoami", headers=_auth(new_key)).status_code == 200


def test_session_is_scoped_to_tenant() -> None:
    tenant_a, key_a = _register_tenant("a")
    _tenant_b, key_b = _register_tenant("b")
    with engine.begin() as conn:
        _ = conn.execute(text(f"SET LOCAL app.tenant_id = '{tenant_a}'"))
        function_id = conn.execute(
            text(
                "INSERT INTO functions (id, tenant_id, name, runtime) VALUES (:id, :tid, 'a-func', 'python-3.11') RETURNING id"
            ),
            {"id": uuid.uuid4(), "tid": str(tenant_a)},
        ).scalar_one()

    assert client.get("/functions-count", headers=_auth(key_a)).json() == {"count": 1}
    assert client.get("/functions-count", headers=_auth(key_b)).json() == {"count": 0}
    # Tenant B must not see tenant A's row even with the exact id.
    assert client.get(f"/function/{function_id}", headers=_auth(key_b)).json() == {
        "found": False
    }
    assert client.get(f"/function/{function_id}", headers=_auth(key_a)).json() == {
        "found": True
    }

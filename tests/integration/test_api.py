import uuid

import httpx
from fastapi.testclient import TestClient
from sqlalchemy import text

from dxforge.api.main import create_app
from dxforge.auth.api_keys import hash_key
from dxforge.db.session import engine

from tests.helpers import seed_project_version

client = TestClient(create_app(version="test"))


def _get(path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    return client.get(path, headers=headers)


def _post(
    path: str, json: object = None, headers: dict[str, str] | None = None
) -> httpx.Response:
    return client.post(path, json=json, headers=headers)


def _put(path: str, json: object, headers: dict[str, str] | None = None) -> httpx.Response:
    return client.put(path, json=json, headers=headers)


def _delete(path: str, headers: dict[str, str] | None = None) -> httpx.Response:
    return client.delete(path, headers=headers)


def _register(name: str = "t") -> dict[str, str]:
    response = _post("/api/v1/tenants", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _function_payload(project_id: str, version_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "name": "nightly",
        "project_id": project_id,
        "version_id": version_id,
        "command": ["python", "main.py"],
        "description": "d",
    }
    payload.update(overrides)
    return payload


def test_health_and_ready() -> None:
    assert _get("/api/v1/health").json() == {"status": "ok"}
    assert _get("/api/v1/ready").json() == {"status": "ok"}


def test_register_tenant_returns_key_once() -> None:
    tenant = _register("acme")
    assert set(tenant) == {"id", "name", "api_key"}
    assert tenant["name"] == "acme"
    with engine.connect() as conn:
        stored: str = conn.execute(
            text("SELECT api_key_hash FROM tenants WHERE id = :id"),
            {"id": uuid.UUID(tenant["id"])},
        ).scalar_one()
    assert stored == hash_key(tenant["api_key"])


def test_register_requires_name() -> None:
    assert _post("/api/v1/tenants", json={}).status_code == 422


def test_protected_routes_require_auth() -> None:
    assert _get("/api/v1/functions").status_code == 401
    assert _get("/api/v1/projects").status_code == 401
    assert _post("/api/v1/functions", json={"name": "x"}).status_code == 401


def test_project_crud_and_isolation() -> None:
    tenant_a = _register("a")
    tenant_b = _register("b")
    headers_a = _auth(tenant_a["api_key"])
    headers_b = _auth(tenant_b["api_key"])

    created = _post("/api/v1/projects", json={"name": "strat-a"}, headers=headers_a)
    assert created.status_code == 201
    project_id = created.json()["id"]

    listed = _get("/api/v1/projects", headers=headers_a).json()
    assert [p["id"] for p in listed] == [project_id]
    assert _get("/api/v1/projects", headers=headers_b).json() == []
    assert _get(f"/api/v1/projects/{project_id}/versions", headers=headers_b).status_code == 404


def test_function_crud_roundtrip() -> None:
    tenant = _register("crud")
    headers = _auth(tenant["api_key"])
    project_id, version_id = seed_project_version(engine, uuid.UUID(tenant["id"]))

    created = _post(
        "/api/v1/functions",
        json=_function_payload(str(project_id), str(version_id)),
        headers=headers,
    )
    assert created.status_code == 201
    body = created.json()
    assert body["name"] == "nightly"
    assert body["description"] == "d"
    assert body["command"] == ["python", "main.py"]
    assert body["project_id"] == str(project_id)
    assert body["version_id"] == str(version_id)
    function_id = body["id"]

    listed = _get("/api/v1/functions", headers=headers).json()
    assert [f["id"] for f in listed] == [function_id]

    fetched = _get(f"/api/v1/functions/{function_id}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["command"] == ["python", "main.py"]

    updated = _put(
        f"/api/v1/functions/{function_id}",
        json=_function_payload(
            str(project_id), str(version_id), description="updated", command=["python", "train.py"]
        ),
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "updated"
    assert updated.json()["command"] == ["python", "train.py"]

    assert _delete(f"/api/v1/functions/{function_id}", headers=headers).status_code == 204
    assert _get(f"/api/v1/functions/{function_id}", headers=headers).status_code == 404


def test_cross_tenant_isolation() -> None:
    tenant_a = _register("a")
    tenant_b = _register("b")
    headers_a = _auth(tenant_a["api_key"])
    headers_b = _auth(tenant_b["api_key"])

    project_id, version_id = seed_project_version(engine, uuid.UUID(tenant_a["id"]))
    function_id = _post(
        "/api/v1/functions",
        json=_function_payload(str(project_id), str(version_id)),
        headers=headers_a,
    ).json()["id"]

    assert _get("/api/v1/functions", headers=headers_b).json() == []
    assert _get(f"/api/v1/functions/{function_id}", headers=headers_b).status_code == 404
    assert (
        _put(
            f"/api/v1/functions/{function_id}",
            json=_function_payload(str(project_id), str(version_id)),
            headers=headers_b,
        ).status_code
        == 404
    )
    assert _delete(f"/api/v1/functions/{function_id}", headers=headers_b).status_code == 404


def test_function_requires_valid_pin() -> None:
    tenant = _register("pin")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = seed_project_version(engine, tenant_id)
    other_project_id, _ = seed_project_version(engine, tenant_id, version_number=2)

    # Version from a different project.
    response = _post(
        "/api/v1/functions",
        json=_function_payload(str(other_project_id), str(version_id)),
        headers=headers,
    )
    assert response.status_code == 400

    # A version that does not exist.
    response = _post(
        "/api/v1/functions",
        json=_function_payload(str(project_id), str(uuid.uuid4())),
        headers=headers,
    )
    assert response.status_code == 400


def test_rotate_key_invalidates_old() -> None:
    tenant = _register("rotate")
    rotated = _post(
        f"/api/v1/tenants/{tenant['id']}/rotate-key", headers=_auth(tenant["api_key"])
    )
    assert rotated.status_code == 200
    new_key = rotated.json()["api_key"]
    assert _get("/api/v1/functions", headers=_auth(tenant["api_key"])).status_code == 401
    assert _get("/api/v1/functions", headers=_auth(new_key)).status_code == 200


def test_cannot_rotate_other_tenant() -> None:
    tenant_a = _register("a")
    tenant_b = _register("b")
    response = _post(
        f"/api/v1/tenants/{tenant_b['id']}/rotate-key", headers=_auth(tenant_a["api_key"])
    )
    assert response.status_code == 404


def test_versions_visible_through_project_and_function() -> None:
    tenant_a = _register("a")
    tenant_b = _register("b")
    headers_a = _auth(tenant_a["api_key"])
    headers_b = _auth(tenant_b["api_key"])
    tenant_id = uuid.UUID(tenant_a["id"])
    project_id, version_id = seed_project_version(engine, tenant_id)

    function_id = _post(
        "/api/v1/functions",
        json=_function_payload(str(project_id), str(version_id)),
        headers=headers_a,
    ).json()["id"]

    own_versions = _get(f"/api/v1/functions/{function_id}/versions", headers=headers_a).json()
    assert [v["id"] for v in own_versions] == [str(version_id)]
    assert own_versions[0]["runtime"] == "python-3.11"

    project_versions = _get(f"/api/v1/projects/{project_id}/versions", headers=headers_a).json()
    assert [v["id"] for v in project_versions] == [str(version_id)]

    assert _get(f"/api/v1/functions/{function_id}/versions", headers=headers_b).status_code == 404
    assert _get(f"/api/v1/projects/{project_id}/versions", headers=headers_b).status_code == 404

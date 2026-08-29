import io
import shutil
import subprocess
import tarfile
import tempfile
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from hvac.exceptions import Forbidden
from sqlalchemy import text

from dxforge.api.main import create_app
from dxforge.build.tools import TOOLS
from dxforge.config import settings
from dxforge.crypto.envelope import decrypt_bytes
from dxforge.crypto.kms_client import (
    build_credential_client,
    build_execution_client,
    build_ingest_client,
)
from dxforge.db.models import GitCredential, Version
from dxforge.db.session import engine, session_factory
from dxforge.storage.object_store import build_execution_store, build_key

pytestmark = pytest.mark.skipif(
    not (
        settings.minio_ingest_secret_key
        and settings.minio_exec_secret_key
        and settings.bao_ingest_token
    ),
    reason="infra not configured (run make setup)",
)

client = TestClient(create_app(version="test"))


def _register(name: str = "t") -> dict[str, str]:
    response = client.post("/api/v1/tenants", json={"name": name})
    assert response.status_code == 201
    return response.json()


def _auth(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def _upload(zip_bytes: bytes) -> str:
    response = client.post(
        "/api/v1/upload",
        files={"file": ("code.zip", zip_bytes, "application/zip")},
    )
    assert response.status_code == 201
    return response.json()["file_id"]


def _create_project(
    headers: dict[str, str], name: str = "p", build_tool: str = "none"
) -> str:
    response = client.post(
        "/api/v1/projects", json={"name": name, "build_tool": build_tool}, headers=headers
    )
    assert response.status_code == 201
    return response.json()["id"]


def _version_row(tenant_id: uuid.UUID, version_id: uuid.UUID) -> Version:
    session = session_factory(tenant_id)
    try:
        return session.get(Version, version_id)
    finally:
        session.close()


def _decrypt_artifact(tenant_id: uuid.UUID, version_id: uuid.UUID) -> bytes:
    version = _version_row(tenant_id, version_id)
    assert version is not None
    ciphertext = build_execution_store().get_object(version.code_object_key)
    with build_execution_client().unwrap_data_key(version.wrapped_dek) as dek:
        return decrypt_bytes(dek, ciphertext)


def test_tools_registry() -> None:
    assert set(TOOLS) == {"none", "make", "docker"}


def test_upload_accepts_zip_rejects_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _upload(_zip({"main.py": b"print(1)"}))
    assert (
        client.post(
            "/api/v1/upload", files={"file": ("x.zip", b"not-a-zip", "application/zip")}
        ).status_code
        == 400
    )
    monkeypatch.setattr(settings, "max_upload_bytes", 16)
    assert (
        client.post(
            "/api/v1/upload", files={"file": ("x.zip", b"a" * 100, "application/zip")}
        ).status_code
        == 413
    )


def test_build_creates_encrypted_version() -> None:
    tenant = _register("build")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id = _create_project(headers)

    payload = _zip({"main.py": b"print('hi')\n"})
    file_id = _upload(payload)
    response = client.post(
        f"/api/v1/projects/{project_id}/build",
        json={"file_id": file_id},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["version_number"] == 1
    assert body["runtime"] == "python-3.11"
    assert body["build_tool"] == "none"

    version = _version_row(tenant_id, uuid.UUID(body["id"]))
    assert version is not None
    assert version.code_object_key == build_key(tenant_id, uuid.UUID(project_id), 1)

    ciphertext = build_execution_store().get_object(version.code_object_key)
    assert ciphertext != payload

    # FR-G7 split at the pipeline level: only the execution token can unwrap.
    with pytest.raises(Forbidden):
        _ = build_ingest_client().unwrap_data_key(version.wrapped_dek)

    artifact = _decrypt_artifact(tenant_id, uuid.UUID(body["id"]))
    with tarfile.open(fileobj=io.BytesIO(artifact), mode="r:gz") as tar:
        assert tar.extractfile("main.py").read() == b"print('hi')\n"


def test_build_rejects_traversal_zip() -> None:
    tenant = _register("traversal")
    headers = _auth(tenant["api_key"])
    project_id = _create_project(headers)
    file_id = _upload(_zip({"../evil.txt": b"boom"}))
    response = client.post(
        f"/api/v1/projects/{project_id}/build",
        json={"file_id": file_id},
        headers=headers,
    )
    assert response.status_code == 400


def test_runtime_inheritance_and_override() -> None:
    tenant = _register("runtime")
    headers = _auth(tenant["api_key"])
    project_id = _create_project(headers)
    file_id = _upload(_zip({"main.py": b"x"}))

    v1 = client.post(
        f"/api/v1/projects/{project_id}/build", json={"file_id": file_id}, headers=headers
    ).json()
    v2 = client.post(
        f"/api/v1/projects/{project_id}/build", json={"file_id": file_id}, headers=headers
    ).json()
    v3 = client.post(
        f"/api/v1/projects/{project_id}/build",
        json={"file_id": file_id, "runtime": "node-20"},
        headers=headers,
    ).json()

    assert v1["runtime"] == "python-3.11"
    assert v2["version_number"] == 2
    assert v2["runtime"] == v1["runtime"]
    assert v3["version_number"] == 3
    assert v3["runtime"] == "node-20"


def test_make_build_tool() -> None:
    if shutil.which("make") is None:
        pytest.skip("make not available")
    tenant = _register("make")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id = _create_project(headers, build_tool="make")

    file_id = _upload(
        _zip(
            {
                "Makefile": b"build:\n\techo hi > out.txt\n",
                "main.py": b"print(1)",
            }
        )
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/build",
        json={"file_id": file_id, "build_command": "build"},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["build_tool"] == "make"

    artifact = _decrypt_artifact(tenant_id, uuid.UUID(body["id"]))
    with tarfile.open(fileobj=io.BytesIO(artifact), mode="r:gz") as tar:
        assert tar.extractfile("out.txt").read() == b"hi\n"


def test_docker_build_tool() -> None:
    import docker as docker_sdk

    try:
        docker_sdk.from_env().ping()
    except Exception:
        pytest.skip("docker daemon not reachable")
    tenant = _register("docker")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id = _create_project(headers, build_tool="docker")

    file_id = _upload(
        _zip(
            {
                "Dockerfile": b"FROM alpine:3.19\nRUN echo built > /out.txt\n",
                "main.py": b"print(1)",
            }
        )
    )
    response = client.post(
        f"/api/v1/projects/{project_id}/build",
        json={"file_id": file_id},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["build_tool"] == "docker"

    artifact = _decrypt_artifact(tenant_id, uuid.UUID(body["id"]))
    with tarfile.open(fileobj=io.BytesIO(artifact), mode="r:") as tar:
        names = tar.getnames()
    assert "manifest.json" in names


def test_credentials_roundtrip() -> None:
    tenant = _register("creds")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    private_key = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc123\n-----END OPENSSH PRIVATE KEY-----\n"

    response = client.post(
        "/api/v1/credentials",
        json={"name": "github", "private_key": private_key},
        headers=headers,
    )
    assert response.status_code == 201
    credential_id = uuid.UUID(response.json()["id"])

    session = session_factory(tenant_id)
    try:
        credential = session.get(GitCredential, credential_id)
    finally:
        session.close()
    assert credential is not None
    with build_credential_client().unwrap_data_key(credential.wrapped_dek) as dek:
        assert decrypt_bytes(dek, credential.ciphertext).decode() == private_key


def test_git_source_build() -> None:
    if shutil.which("git") is None:
        pytest.skip("git not available")
    tenant = _register("git")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id = _create_project(headers)

    repo = Path(tempfile.mkdtemp(prefix="dxforge-repo-"))
    (repo / "main.py").write_text("print('from git')\n")
    subprocess.run(["git", "init", "-q", repo], check=True)
    subprocess.run(
        ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "."],
        check=True,
    )
    subprocess.run(
        ["git", "-C", repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        check=True,
    )
    try:
        response = client.post(
            f"/api/v1/projects/{project_id}/build",
            json={"repo_url": f"file://{repo}"},
            headers=headers,
        )
    finally:
        shutil.rmtree(repo, ignore_errors=True)
    assert response.status_code == 201
    body = response.json()
    assert body["build_tool"] == "none"

    artifact = _decrypt_artifact(tenant_id, uuid.UUID(body["id"]))
    with tarfile.open(fileobj=io.BytesIO(artifact), mode="r:gz") as tar:
        assert tar.extractfile("main.py").read() == b"print('from git')\n"

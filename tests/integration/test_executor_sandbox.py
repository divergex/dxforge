import io
import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dxforge.api.main import create_app
from dxforge.config import settings
from dxforge.db.models import Execution, Schedule, Version
from dxforge.db.session import session_factory
from dxforge.scheduler.dispatcher import dispatch_cycle

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


def _build_project(
    headers: dict[str, str], files: dict[str, bytes], build_tool: str = "none"
) -> tuple[str, str]:
    project = client.post(
        "/api/v1/projects", json={"name": "p", "build_tool": build_tool}, headers=headers
    ).json()
    response = client.post(
        "/api/v1/upload", files={"file": ("code.zip", _zip(files), "application/zip")},
        headers=headers,
    )
    file_id = response.json()["file_id"]
    version = client.post(
        f"/api/v1/projects/{project['id']}/build",
        json={"file_id": file_id},
        headers=headers,
    )
    assert version.status_code == 201
    return project["id"], version.json()["id"]


def _create_function(
    headers: dict[str, str],
    project_id: str,
    version_id: str,
    command: list[str] | None = None,
    name: str = "fn",
) -> str:
    response = client.post(
        "/api/v1/functions",
        json={
            "name": name,
            "project_id": project_id,
            "version_id": version_id,
            "command": command or ["python", "main.py"],
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


def _create_schedule(
    headers: dict[str, str],
    function_id: str,
    rule: str,
    executor_backend: str = "docker",
) -> dict[str, str]:
    response = client.post(
        "/api/v1/schedules",
        json={
            "function_id": function_id,
            "rule": rule,
            "executor_backend": executor_backend,
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()


def _execution_row(tenant_id: uuid.UUID, execution_id: uuid.UUID) -> Execution:
    session = session_factory(tenant_id)
    try:
        execution = session.get(Execution, execution_id)
        assert execution is not None
        return execution
    finally:
        session.close()


def _leftover_ephemeral() -> list[str]:
    tmp = Path(tempfile.gettempdir())
    return sorted(
        p.name
        for p in tmp.iterdir()
        if p.name.startswith(("dxforge-run-", "dxforge-code-"))
    )


def test_schedule_fires_and_runs_code() -> None:
    tenant = _register("fire")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('hello from sandbox')\n"})
    function_id = _create_function(headers, project_id, version_id)
    schedule = _create_schedule(headers, function_id, '{"every": {"days": 1}}')

    created = dispatch_cycle()
    assert len(created) == 1

    execution = _execution_row(tenant_id, created[0])
    assert execution is not None
    assert execution.status == "success"
    assert execution.exit_code == 0
    assert "hello from sandbox" in execution.stdout
    assert execution.duration_seconds is not None

    # Schedule records last_fired and does not re-fire on the same cycle.
    session = session_factory(tenant_id)
    try:
        schedule_row = session.get(Schedule, uuid.UUID(schedule["id"]))
        assert schedule_row is not None
        assert schedule_row.last_fired_at is not None
    finally:
        session.close()
    assert dispatch_cycle() == []
    assert _leftover_ephemeral() == []


def test_failed_execution_captures_stderr() -> None:
    tenant = _register("fail")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(
        headers, {"main.py": b"import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n"}
    )
    function_id = _create_function(headers, project_id, version_id)
    _create_schedule(headers, function_id, '{"every": {"days": 1}}')

    created = dispatch_cycle()
    execution = _execution_row(tenant_id, created[0])
    assert execution.status == "failed"
    assert execution.exit_code == 3
    assert "boom" in execution.stderr
    assert _leftover_ephemeral() == []


def test_timeout_kills_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    tenant = _register("timeout")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"import time\ntime.sleep(30)\n"})
    function_id = _create_function(headers, project_id, version_id)
    _create_schedule(headers, function_id, '{"every": {"days": 1}}')

    monkeypatch.setattr(settings, "execution_timeout_seconds", 2)
    created = dispatch_cycle()
    execution = _execution_row(tenant_id, created[0])
    assert execution.status in ("failed", "timeout")
    assert execution.exit_code == 124
    assert _leftover_ephemeral() == []


def test_executions_api_and_logs() -> None:
    tenant = _register("api")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('logged')\n"})
    function_id = _create_function(headers, project_id, version_id)
    schedule = _create_schedule(headers, function_id, '{"every": {"days": 1}}')

    created = dispatch_cycle()
    execution_id = created[0]

    listing = client.get(
        f"/api/v1/executions?schedule_id={schedule['id']}", headers=headers
    )
    assert listing.status_code == 200
    assert [e["id"] for e in listing.json()] == [str(execution_id)]
    assert "stdout" not in listing.json()[0]
    assert listing.json()[0]["executor_backend"] == "docker"

    logs = client.get(f"/api/v1/executions/{execution_id}/logs", headers=headers)
    assert logs.status_code == 200
    assert "logged" in logs.json()["stdout"]
    assert _leftover_ephemeral() == []


def test_host_executor_runs_code() -> None:
    from dxforge.executor.host_executor import HostExecutor
    from dxforge.executor.sandbox import fetch_decrypt_to_file
    from dxforge.db.session import session_factory

    tenant = _register("host-run")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('host marker')\n"})
    session = session_factory(tenant_id)
    try:
        version = session.get(Version, uuid.UUID(version_id))
        assert version is not None
        artifact = fetch_decrypt_to_file(version)
        try:
            result = HostExecutor().run(artifact, version, ["python", "main.py"], 30)
        finally:
            shutil.rmtree(artifact.parent, ignore_errors=True)
    finally:
        session.close()
    assert result.exit_code == 0
    assert "host marker" in result.stdout
    assert _leftover_ephemeral() == []


def test_docker_build_tool_execution() -> None:
    import docker as docker_sdk

    try:
        docker_sdk.from_env().ping()
    except Exception:
        pytest.skip("docker daemon not reachable")
    tenant = _register("docker-run")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(
        headers,
        {"Dockerfile": b"FROM alpine:3.19\nCMD echo from-image\n", "main.py": b""},
        build_tool="docker",
    )
    function_id = _create_function(headers, project_id, version_id)
    _create_schedule(headers, function_id, '{"every": {"days": 1}}')

    created = dispatch_cycle()
    execution = _execution_row(tenant_id, created[0])
    assert execution.status == "success"
    assert execution.exit_code == 0
    assert "from-image" in execution.stdout
    assert _leftover_ephemeral() == []


def test_command_with_arguments() -> None:
    tenant = _register("argv")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(
        headers,
        {"main.py": b"import sys\nprint('argv:', sys.argv[1:])\n"},
    )
    function_id = _create_function(
        headers, project_id, version_id, ["python", "main.py", "--flag", "val"]
    )
    _create_schedule(headers, function_id, '{"every": {"days": 1}}')

    created = dispatch_cycle()
    execution = _execution_row(tenant_id, created[0])
    assert execution.status == "success"
    assert "argv: ['--flag', 'val']" in execution.stdout


def test_host_backend_schedule() -> None:
    tenant = _register("host-backend")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(
        headers, {"main.py": b"print('ran on host')\n"}
    )
    function_id = _create_function(headers, project_id, version_id)
    _create_schedule(headers, function_id, '{"every": {"days": 1}}', executor_backend="host")

    created = dispatch_cycle()
    execution = _execution_row(tenant_id, created[0])
    assert execution.status == "success"
    assert execution.executor_backend == "host"
    assert "ran on host" in execution.stdout
    assert _leftover_ephemeral() == []


def test_schedule_rejects_unknown_backend() -> None:
    tenant = _register("bad-backend")
    headers = _auth(tenant["api_key"])
    project_id, version_id = _build_project(headers, {"main.py": b"x"})
    function_id = _create_function(headers, project_id, version_id)

    response = client.post(
        "/api/v1/schedules",
        json={
            "function_id": function_id,
            "rule": '{"every": {"hours": 1}}',
            "executor_backend": "k8s",
        },
        headers=headers,
    )
    assert response.status_code == 422


def test_schedule_crud_and_isolation() -> None:
    tenant_a = _register("a")
    tenant_b = _register("b")
    headers_a = _auth(tenant_a["api_key"])
    headers_b = _auth(tenant_b["api_key"])
    project_id, version_id = _build_project(headers_a, {"main.py": b"x"})
    function_id = _create_function(headers_a, project_id, version_id)

    created = client.post(
        "/api/v1/schedules",
        json={"function_id": function_id, "rule": '{"every": {"hours": 1}}'},
        headers=headers_a,
    ).json()

    assert client.get("/api/v1/schedules", headers=headers_b).json() == []
    assert (
        client.get(f"/api/v1/schedules/{created['id']}", headers=headers_b).status_code
        == 404
    )
    assert (
        client.put(
            f"/api/v1/schedules/{created['id']}",
            json={"function_id": function_id, "rule": '{"every": {"hours": 2}}'},
            headers=headers_b,
        ).status_code
        == 404
    )
    assert (
        client.delete(f"/api/v1/schedules/{created['id']}", headers=headers_b).status_code
        == 404
    )

    updated = client.put(
        f"/api/v1/schedules/{created['id']}",
        json={"function_id": function_id, "rule": '{"every": {"hours": 2}}'},
        headers=headers_a,
    )
    assert updated.status_code == 200
    assert updated.json()["rule"] == '{"every": {"hours": 2}}'

    assert (
        client.post(
            "/api/v1/schedules",
            json={"function_id": function_id, "rule": "not json"},
            headers=headers_a,
        ).status_code
        == 422
    )
    assert (
        client.delete(f"/api/v1/schedules/{created['id']}", headers=headers_a).status_code
        == 204
    )

import io
import os
import signal
import socket
import tempfile
import threading
import time
import uuid
import zipfile
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dxforge.api.main import create_app
from dxforge.config import settings
from dxforge.db.models import Execution, Schedule
from dxforge.db.session import session_factory
from dxforge.executor import run_dir
from dxforge.scheduler import wakeup
from dxforge.scheduler.cron import utcnow
from dxforge.scheduler.dispatcher import (
    dispatch_cycle,
    dispatch_schedule,
    reconcile_executions,
)

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
    **extra: object,
) -> str:
    response = client.post(
        "/api/v1/functions",
        json={
            "name": name,
            "project_id": project_id,
            "version_id": version_id,
            "command": command or ["python", "main.py"],
            **extra,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def _create_schedule(
    headers: dict[str, str],
    function_id: str,
    rule: str | None = None,
    executor_backend: str | None = None,
) -> dict[str, str]:
    body: dict[str, object] = {"function_id": function_id, "rule": rule}
    if executor_backend is not None:
        body["executor_backend"] = executor_backend
    response = client.post("/api/v1/schedules", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _fire(tenant_id: uuid.UUID, schedule: dict[str, str]) -> uuid.UUID:
    execution_id = dispatch_schedule(tenant_id, uuid.UUID(schedule["id"]))
    assert execution_id is not None
    return execution_id


def _execution_row(tenant_id: uuid.UUID, execution_id: uuid.UUID) -> Execution:
    session = session_factory(tenant_id)
    try:
        execution = session.get(Execution, execution_id)
        assert execution is not None
        return execution
    finally:
        session.close()


def _wait_for(condition: Callable[[], bool], what: str, timeout: float = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(0.1)
    raise AssertionError(f"timed out waiting for {what}")


def _wait_finished(tenant_id: uuid.UUID, execution_id: uuid.UUID) -> Execution:
    _wait_for(
        lambda: _execution_row(tenant_id, execution_id).status != "running",
        f"execution {execution_id} to finish",
    )
    return _execution_row(tenant_id, execution_id)


def _schedule_row(tenant_id: uuid.UUID, schedule_id: str) -> Schedule:
    session = session_factory(tenant_id)
    try:
        schedule = session.get(Schedule, uuid.UUID(schedule_id))
        assert schedule is not None
        return schedule
    finally:
        session.close()


def _leftover_ephemeral() -> list[str]:
    tmp = Path(tempfile.gettempdir())
    return sorted(p.name for p in tmp.iterdir() if p.name.startswith("dxforge-run-"))


def _process_gone(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return True
    return state == "Z"


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _service_files(port: int, *, healthy: bool = True) -> dict[str, bytes]:
    """A tiny HTTP service: /health answers 200 (or never answers when healthy=False)."""
    handler = (
        "self.send_response(200); self.end_headers(); self.wfile.write(b'ok')"
        if healthy
        else "import time; time.sleep(3600)"
    )
    code = (
        "import http.server, threading\n"
        "class H(http.server.BaseHTTPRequestHandler):\n"
        f"    def do_GET(self): {handler}\n"
        "    def log_message(self, *a): pass\n"
        "print('service up', flush=True)\n"
        f"http.server.ThreadingHTTPServer(('127.0.0.1', {port}), H).serve_forever()\n"
    )
    return {"main.py": code.encode()}


@pytest.fixture
def fast_supervisor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Supervisors are separate processes: they read these from the environment."""
    monkeypatch.setenv("FORGE_SUPERVISOR_HEARTBEAT_SECONDS", "0.3")
    monkeypatch.setenv("FORGE_HEALTH_CHECK_INTERVAL_SECONDS", "0.3")
    monkeypatch.setenv("FORGE_STOP_GRACE_SECONDS", "2")


def test_schedule_fires_and_runs_code() -> None:
    tenant = _register("fire")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('hello from sandbox')\n"})
    function_id = _create_function(headers, project_id, version_id)
    schedule = _create_schedule(headers, function_id, '{"every": {"days": 1}}')
    assert schedule["trigger_at"] is not None

    # dispatch_cycle returns without waiting for the code to run.
    created = dispatch_cycle()
    listing = client.get(f"/api/v1/executions?schedule_id={schedule['id']}", headers=headers)
    mine = [uuid.UUID(e["id"]) for e in listing.json()]
    assert len(mine) == 1 and mine[0] in created
    execution = _wait_finished(tenant_id, mine[0])
    assert execution.status == "success"
    assert execution.exit_code == 0
    assert "hello from sandbox" in execution.stdout
    assert execution.duration_seconds is not None
    assert execution.executor_backend == "host"
    assert not run_dir.run_dir(execution.id).exists()

    row = _schedule_row(tenant_id, schedule["id"])
    assert row.last_fired_at is not None
    assert row.trigger_at is None
    assert dispatch_schedule(tenant_id, uuid.UUID(schedule["id"])) is None
    assert _leftover_ephemeral() == []


def test_failed_execution_captures_stderr() -> None:
    tenant = _register("fail")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(
        headers, {"main.py": b"import sys\nprint('boom', file=sys.stderr)\nsys.exit(3)\n"}
    )
    function_id = _create_function(headers, project_id, version_id)
    execution = _wait_finished(tenant_id, _fire(tenant_id, _create_schedule(headers, function_id)))
    assert execution.status == "failed"
    assert execution.exit_code == 3
    assert "boom" in execution.stderr
    assert _leftover_ephemeral() == []


def test_unstartable_command_fails_with_message() -> None:
    tenant = _register("nocmd")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b""})
    function_id = _create_function(headers, project_id, version_id, ["./does-not-exist"])
    execution = _wait_finished(tenant_id, _fire(tenant_id, _create_schedule(headers, function_id)))
    assert execution.status == "failed"
    assert execution.exit_code == 127
    assert "does-not-exist" in execution.stderr


def test_hard_timeout_kills_execution() -> None:
    tenant = _register("timeout")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"import time\ntime.sleep(60)\n"})
    function_id = _create_function(headers, project_id, version_id, hard_timeout_seconds=2)
    execution = _wait_finished(tenant_id, _fire(tenant_id, _create_schedule(headers, function_id)))
    assert execution.status == "timeout"
    assert execution.exit_code == 124
    assert _leftover_ephemeral() == []


def test_function_defaults_to_the_configured_hard_timeout_and_accepts_none() -> None:
    tenant = _register("timeout-field")
    headers = _auth(tenant["api_key"])
    project_id, version_id = _build_project(headers, {"main.py": b""})
    base = {"name": "f", "project_id": project_id, "version_id": version_id, "command": ["x"]}

    default = client.post("/api/v1/functions", json=base, headers=headers).json()
    assert default["hard_timeout_seconds"] == settings.execution_timeout_seconds

    never = client.post(
        "/api/v1/functions", json={**base, "hard_timeout_seconds": None}, headers=headers
    ).json()
    assert never["hard_timeout_seconds"] is None


def test_health_url_must_be_loopback() -> None:
    tenant = _register("health-ssrf")
    headers = _auth(tenant["api_key"])
    project_id, version_id = _build_project(headers, {"main.py": b""})
    for url in ("http://169.254.169.254/latest", "http://example.com/health", "file:///etc/passwd"):
        response = client.post(
            "/api/v1/functions",
            json={
                "name": "f", "project_id": project_id, "version_id": version_id,
                "command": ["x"], "health_url": url,
            },
            headers=headers,
        )
        assert response.status_code == 422, url


def test_executions_api_and_logs() -> None:
    tenant = _register("api")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('logged')\n"})
    function_id = _create_function(headers, project_id, version_id)
    schedule = _create_schedule(headers, function_id)
    execution_id = _fire(tenant_id, schedule)
    _ = _wait_finished(tenant_id, execution_id)

    listing = client.get(
        f"/api/v1/executions?schedule_id={schedule['id']}", headers=headers
    )
    assert listing.status_code == 200
    assert [e["id"] for e in listing.json()] == [str(execution_id)]
    assert "stdout" not in listing.json()[0]
    assert listing.json()[0]["executor_backend"] == "host"

    logs = client.get(f"/api/v1/executions/{execution_id}/logs", headers=headers)
    assert logs.status_code == 200
    assert "logged" in logs.json()["stdout"]
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
    schedule = _create_schedule(headers, function_id, executor_backend="docker")
    execution = _wait_finished(tenant_id, _fire(tenant_id, schedule))
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
    execution = _wait_finished(tenant_id, _fire(tenant_id, _create_schedule(headers, function_id)))
    assert execution.status == "success"
    assert "argv: ['--flag', 'val']" in execution.stdout


def test_run_once_schedule_fires_at_submit_and_again_only_after_update() -> None:
    tenant = _register("once")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('once')\n"})
    function_id = _create_function(headers, project_id, version_id)
    schedule = _create_schedule(headers, function_id, rule=None)
    assert schedule["rule"] is None

    first = _fire(tenant_id, schedule)
    assert _wait_finished(tenant_id, first).status == "success"
    assert dispatch_schedule(tenant_id, uuid.UUID(schedule["id"])) is None
    assert _schedule_row(tenant_id, schedule["id"]).trigger_at is None

    updated = client.put(
        f"/api/v1/schedules/{schedule['id']}",
        json={"function_id": function_id, "rule": None},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["trigger_at"] is not None

    second = _fire(tenant_id, schedule)
    assert second != first
    assert _wait_finished(tenant_id, second).status == "success"
    assert dispatch_schedule(tenant_id, uuid.UUID(schedule["id"])) is None


def test_disabled_schedule_is_never_armed() -> None:
    tenant = _register("disabled")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('x')\n"})
    function_id = _create_function(headers, project_id, version_id)
    response = client.post(
        "/api/v1/schedules",
        json={"function_id": function_id, "enabled": False},
        headers=headers,
    )
    schedule = response.json()
    assert schedule["trigger_at"] is None
    assert dispatch_schedule(tenant_id, uuid.UUID(schedule["id"])) is None


def test_concurrent_dispatchers_fire_an_occurrence_once() -> None:
    tenant = _register("race")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('race')\n"})
    function_id = _create_function(headers, project_id, version_id)
    schedule = _create_schedule(headers, function_id)

    results: list[uuid.UUID | None] = []
    barrier = threading.Barrier(6)

    def attempt() -> None:
        _ = barrier.wait()
        results.append(dispatch_schedule(tenant_id, uuid.UUID(schedule["id"])))

    threads = [threading.Thread(target=attempt) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    fired = [r for r in results if r is not None]
    assert len(fired) == 1
    listing = client.get(f"/api/v1/executions?schedule_id={schedule['id']}", headers=headers)
    assert len(listing.json()) == 1
    _ = _wait_finished(tenant_id, fired[0])


def test_submitting_a_schedule_notifies_the_worker() -> None:
    tenant = _register("wakeup")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"print('x')\n"})
    function_id = _create_function(headers, project_id, version_id)

    listener = wakeup.Listener()
    try:
        schedule = _create_schedule(headers, function_id)
        payloads = listener.wait(10)
    finally:
        listener.close()
    assert wakeup.parse(payloads[0]) == (tenant_id, uuid.UUID(schedule["id"]))
    _ = _wait_finished(tenant_id, _fire(tenant_id, schedule))


def test_unhealthy_service_is_killed_without_a_hard_timeout(fast_supervisor: None) -> None:
    tenant = _register("unhealthy")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    port = _free_port()
    project_id, version_id = _build_project(headers, _service_files(port, healthy=False))
    function_id = _create_function(
        headers, project_id, version_id,
        health_url=f"http://127.0.0.1:{port}/health",
        alive_timeout_seconds=2,
        hard_timeout_seconds=None,
    )
    execution = _wait_finished(tenant_id, _fire(tenant_id, _create_schedule(headers, function_id)))
    assert execution.status == "unhealthy"
    assert execution.exit_code == 124
    assert "service up" in execution.stdout


def test_service_runs_past_any_timeout_until_stopped(fast_supervisor: None) -> None:
    tenant = _register("service")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    port = _free_port()
    project_id, version_id = _build_project(headers, _service_files(port))
    function_id = _create_function(
        headers, project_id, version_id,
        health_url=f"http://127.0.0.1:{port}/health",
        alive_timeout_seconds=2,
        hard_timeout_seconds=None,
    )
    execution_id = _fire(tenant_id, _create_schedule(headers, function_id))
    url = f"/api/v1/executions/{execution_id}"

    _wait_for(lambda: client.get(f"{url}/logs", headers=headers).json()["stdout"] != "", "live logs")
    assert "service up" in client.get(f"{url}/logs", headers=headers).json()["stdout"]

    # Outlives alive_timeout: health checks keep it alive.
    time.sleep(4)
    running = client.get(url, headers=headers).json()
    assert running["status"] == "running"
    assert running["heartbeat_at"] is not None

    stop = client.post(f"{url}/stop", headers=headers)
    assert stop.status_code == 202
    assert stop.json()["stop_requested"] is True
    execution = _wait_finished(tenant_id, execution_id)
    assert execution.status == "stopped"
    assert "service up" in execution.stdout
    assert execution.pid is not None and _process_gone(execution.pid)
    assert client.post(f"{url}/stop", headers=headers).status_code == 409


def test_execution_survives_dispatcher_and_is_adopted_or_closed_by_reconcile(
    fast_supervisor: None,
) -> None:
    tenant = _register("recover")
    headers = _auth(tenant["api_key"])
    tenant_id = uuid.UUID(tenant["id"])
    project_id, version_id = _build_project(headers, {"main.py": b"import time\nprint('up', flush=True)\ntime.sleep(3600)\n"})
    function_id = _create_function(
        headers, project_id, version_id, hard_timeout_seconds=None
    )
    execution_id = _fire(tenant_id, _create_schedule(headers, function_id))
    _wait_for(lambda: _execution_row(tenant_id, execution_id).pid is not None, "process start")
    row = _execution_row(tenant_id, execution_id)
    assert row.supervisor_pid is not None and row.pid is not None

    # A restarted dispatcher far in the future still finds the supervisor alive: adopt.
    later = utcnow() + timedelta(seconds=settings.supervisor_stale_seconds * 2)
    assert execution_id not in reconcile_executions(now=later)
    assert _execution_row(tenant_id, execution_id).status == "running"

    # Supervisor crash: its process dies with it and reconcile closes the execution.
    os.kill(row.supervisor_pid, signal.SIGKILL)
    _wait_for(lambda: _process_gone(row.pid or 0), "child to die with supervisor")
    assert execution_id in reconcile_executions(now=later)
    closed = _execution_row(tenant_id, execution_id)
    assert closed.status == "lost"
    assert "up" in closed.stdout
    assert not run_dir.run_dir(execution_id).exists()


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

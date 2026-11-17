import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import override

import pytest

from dxforge.executor import host_process
from dxforge.executor.host_process import Outcome


def _run(
    tmp_path: Path,
    command: list[str],
    *,
    hard_timeout: float | None = None,
    health_url: str | None = None,
    alive_timeout: float = 30,
    should_stop: bool | list[bool] = False,
) -> Outcome:
    stops = iter(should_stop) if isinstance(should_stop, list) else None
    with (tmp_path / "out").open("wb") as out, (tmp_path / "err").open("wb") as err:
        process = host_process.spawn(command, tmp_path, out, err)
        return host_process.supervise(
            process,
            hard_timeout_seconds=hard_timeout,
            health_url=health_url,
            alive_timeout_seconds=alive_timeout,
            health_interval_seconds=0.2,
            grace_seconds=2,
            should_stop=(lambda: next(stops, True)) if stops is not None else (lambda: bool(should_stop)),
            tick_seconds=0.05,
        )


class _Health(BaseHTTPRequestHandler):
    status: int = 200

    def do_GET(self) -> None:  # noqa: N802 - http.server dispatch name
        self.send_response(type(self).status)
        self.end_headers()

    @override
    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture
def health_server() -> Iterator[tuple[str, type[_Health]]]:
    handler = type("Handler", (_Health,), {"status": 200})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}/health", handler
    server.shutdown()


def test_exit_code_maps_to_status(tmp_path: Path) -> None:
    assert _run(tmp_path, ["sh", "-c", "exit 0"]) == Outcome("success", 0)
    assert _run(tmp_path, ["sh", "-c", "exit 3"]) == Outcome("failed", 3)


def test_hard_timeout_kills_and_none_never_does(tmp_path: Path) -> None:
    started = time.monotonic()
    outcome = _run(tmp_path, ["sleep", "30"], hard_timeout=0.5)
    assert outcome == Outcome("timeout", host_process.TIMEOUT_EXIT_CODE)
    assert time.monotonic() - started < 10

    assert _run(tmp_path, ["sleep", "1"], hard_timeout=None) == Outcome("success", 0)


def test_unanswered_health_check_kills_as_unhealthy(tmp_path: Path) -> None:
    started = time.monotonic()
    outcome = _run(
        tmp_path, ["sleep", "30"], health_url="http://127.0.0.1:9/health", alive_timeout=1
    )
    assert outcome.status == "unhealthy"
    assert time.monotonic() - started < 10


def test_healthy_process_outlives_alive_timeout(
    tmp_path: Path, health_server: tuple[str, type[_Health]]
) -> None:
    url, _ = health_server
    outcome = _run(tmp_path, ["sleep", "2.5"], health_url=url, alive_timeout=1)
    assert outcome == Outcome("success", 0)


def test_process_that_stops_answering_is_killed(
    tmp_path: Path, health_server: tuple[str, type[_Health]]
) -> None:
    url, handler = health_server
    threading.Timer(0.8, lambda: setattr(handler, "status", 503)).start()
    outcome = _run(tmp_path, ["sleep", "30"], health_url=url, alive_timeout=1)
    assert outcome.status == "unhealthy"


def test_stop_request_terminates_whole_process_group(tmp_path: Path) -> None:
    pid_file = tmp_path / "grandchild.pid"
    command = ["sh", "-c", f"sleep 30 & echo $! > {pid_file}; wait"]
    outcome = _run(tmp_path, command, should_stop=[False, False, False, True])
    assert outcome.status == "stopped"
    grandchild = int(pid_file.read_text())
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not _gone(grandchild):
        time.sleep(0.05)
    assert _gone(grandchild)


def _gone(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return True
    return state == "Z"


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="PR_SET_PDEATHSIG")
def test_child_dies_with_its_supervisor(tmp_path: Path) -> None:
    script = (
        "import os, time\n"
        "from pathlib import Path\n"
        "from dxforge.executor import host_process\n"
        "null = open(os.devnull, 'wb')\n"
        "p = host_process.spawn(['sleep', '60'], Path('.'), null, null)\n"
        "print(p.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    supervisor = subprocess.Popen(
        [sys.executable, "-c", script], stdout=subprocess.PIPE, cwd=tmp_path
    )
    assert supervisor.stdout is not None
    child = int(supervisor.stdout.readline())
    assert not _gone(child)
    supervisor.kill()
    _ = supervisor.wait()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not _gone(child):
        time.sleep(0.05)
    assert _gone(child)

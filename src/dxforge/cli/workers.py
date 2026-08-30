import json
import os
import signal
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict, cast

WORKERS_DIR = Path(__file__).resolve().parents[3] / "var" / "workers"
_REPO_ROOT = WORKERS_DIR.parents[1]


class _WorkerRecord(TypedDict):
    worker_id: str
    pid: int
    started_at: str
    interval: float


@dataclass
class WorkerInfo:
    worker_id: str
    pid: int
    started_at: str
    interval: float
    status: str  # running | stopped


def _alive(pid: int) -> bool:
    try:
        _ = os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _write(info: WorkerInfo) -> None:
    _ = (WORKERS_DIR / f"{info.worker_id}.json").write_text(
        json.dumps(
            {
                "worker_id": info.worker_id,
                "pid": info.pid,
                "started_at": info.started_at,
                "interval": info.interval,
            }
        )
    )


def start(interval: float) -> WorkerInfo:
    """Spawn a detached scheduler worker and register it in var/workers/."""
    WORKERS_DIR.mkdir(parents=True, exist_ok=True)
    existing = [w for w in list_workers() if w.status == "running"]
    if existing:
        message = f"worker {existing[0].worker_id} (pid {existing[0].pid}) is already running. "
        message += "Stop it first. Without leader election two workers would double-fire schedules"
        raise RuntimeError(message)
    worker_id = uuid.uuid4().hex[:8]
    log_path = WORKERS_DIR / f"{worker_id}.log"
    with log_path.open("wb") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "dxforge.cli.main",
                "worker-run",
                "--interval",
                str(interval),
            ],
            cwd=_REPO_ROOT,
            start_new_session=True,
            stdout=log,
            stderr=log,
        )
    time.sleep(0.5)
    if not _alive(process.pid):
        raise RuntimeError(f"worker exited immediately; see {log_path}")
    info = WorkerInfo(
        worker_id, process.pid, _now(), interval, "running"
    )
    _write(info)
    return info


def _read(info_path: Path) -> WorkerInfo:
    data = cast(_WorkerRecord, json.loads(info_path.read_text()))
    pid = int(data["pid"])
    return WorkerInfo(
        worker_id=str(data["worker_id"]),
        pid=pid,
        started_at=str(data["started_at"]),
        interval=float(data["interval"]),
        status="running" if _alive(pid) else "stopped",
    )


def list_workers() -> list[WorkerInfo]:
    if not WORKERS_DIR.exists():
        return []
    return [_read(path) for path in sorted(WORKERS_DIR.glob("*.json"))]


def stop(worker_id: str) -> WorkerInfo | None:
    path = WORKERS_DIR / f"{worker_id}.json"
    if not path.exists():
        return None
    info = _read(path)
    if info.status == "running":
        _ = os.kill(info.pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _alive(info.pid):
            time.sleep(0.1)
        if _alive(info.pid):
            _ = os.kill(info.pid, signal.SIGKILL)
    path.unlink(missing_ok=True)
    info.status = "stopped"
    return info


def _now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")

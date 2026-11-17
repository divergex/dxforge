"""Per-execution runtime directory shared by dispatcher, supervisor and API.

Layout: <execution_dir>/<execution_id>/{code/, stdout.log, stderr.log, supervisor.log}
"""

import shutil
import uuid
from pathlib import Path

from dxforge.config import settings


def run_dir(execution_id: uuid.UUID) -> Path:
    return Path(settings.execution_dir) / str(execution_id)


def create(execution_id: uuid.UUID) -> Path:
    path = run_dir(execution_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_logs(execution_id: uuid.UUID) -> tuple[str, str]:
    """Head of each log, capped at log_max_bytes; empty when the files are gone."""
    path = run_dir(execution_id)
    return _read(path / "stdout.log"), _read(path / "stderr.log")


def remove(execution_id: uuid.UUID) -> None:
    shutil.rmtree(run_dir(execution_id), ignore_errors=True)


def _read(path: Path) -> str:
    try:
        with path.open("rb") as stream:
            return stream.read(settings.log_max_bytes).decode(errors="replace")
    except OSError:
        return ""

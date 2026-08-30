import os
import resource
import shutil
import subprocess
import tarfile
import tempfile
import time
from pathlib import Path
from typing import override

from dxforge.db.models import Version
from dxforge.executor.base import ExecutionResult, Executor

NOBODY_UID = 65534
NOBODY_GID = 65534


def sandbox_preexec() -> None:
    if os.geteuid() != 0:
        return
    os.setgroups([])
    os.setgid(NOBODY_GID)
    os.setuid(NOBODY_UID)
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def run_sandboxed(
    command: list[str],
    cwd: Path,
    timeout_seconds: int,
) -> ExecutionResult:
    """Run a command with dropped privileges and rlimits; used when Docker is unavailable."""
    started = time.monotonic()
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            cwd=cwd,
            timeout=timeout_seconds,
            preexec_fn=sandbox_preexec,
        )
    except subprocess.TimeoutExpired as exc:
        return ExecutionResult(
            exit_code=124,
            stdout=(exc.stdout or b"").decode(errors="replace"),
            stderr=(exc.stderr or b"").decode(errors="replace"),
            duration_seconds=time.monotonic() - started,
        )
    return ExecutionResult(
        exit_code=process.returncode,
        stdout=process.stdout.decode(errors="replace"),
        stderr=process.stderr.decode(errors="replace"),
        duration_seconds=time.monotonic() - started,
    )


class HostExecutor(Executor):
    """Runs extracted source on the host inside the sandbox preexec (no Docker)."""

    @override
    def run(
        self, artifact: Path, version: Version, command: list[str], timeout_seconds: int
    ) -> ExecutionResult:
        code_dir = Path(tempfile.mkdtemp(prefix="dxforge-code-"))
        try:
            with tarfile.open(artifact, "r:gz") as tar:
                tar.extractall(code_dir, filter="data")
            return run_sandboxed(command, code_dir, timeout_seconds)
        finally:
            shutil.rmtree(code_dir, ignore_errors=True)

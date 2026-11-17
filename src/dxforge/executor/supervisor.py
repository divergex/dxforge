"""Detached per-execution supervisor: `python -m dxforge.executor.supervisor TENANT EXECUTION`.

Spawned by the dispatcher in its own session, so it keeps running (and keeps
managing its process) when the API or the scheduler worker stops. It talks to the
database directly: heartbeat, stop requests, final result. The dispatcher's
reconciliation adopts or closes it after a restart (see scheduler/dispatcher.py).
"""

import logging
import shutil
import signal
import sys
import tarfile
import time
import traceback
import uuid
from dataclasses import dataclass
from types import FrameType
from typing import final

from dxforge.config import settings
from dxforge.db.models import Execution, Function, Version
from dxforge.db.session import session_factory
from dxforge.executor import EXECUTORS, HOST, host_process, run_dir
from dxforge.executor.host_process import Outcome
from dxforge.executor.sandbox import fetch_decrypt_to_file
from dxforge.scheduler.cron import utcnow

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Job:
    command: list[str]
    backend: str
    version: Version
    hard_timeout_seconds: int | None
    health_url: str | None
    alive_timeout_seconds: int


@final
class Supervisor:
    def __init__(self, tenant_id: uuid.UUID, execution_id: uuid.UUID) -> None:
        self._tenant_id = tenant_id
        self._execution_id = execution_id
        self._signalled = False
        self._stop_requested = False
        self._next_beat = 0.0
        self._started = time.monotonic()

    def run(self) -> int:
        _ = signal.signal(signal.SIGTERM, self._on_signal)
        _ = signal.signal(signal.SIGINT, self._on_signal)
        _ = run_dir.create(self._execution_id)
        try:
            job = self._load_job()
            outcome = self._run(job)
        except Exception:
            self._append_stderr(traceback.format_exc())
            outcome = Outcome("failed", 1)
        self._finish(outcome)
        return 0

    def _on_signal(self, _signum: int, _frame: FrameType | None) -> None:
        self._signalled = True

    def _load_job(self) -> _Job:
        session = session_factory(self._tenant_id)
        try:
            execution = session.get(Execution, self._execution_id)
            if execution is None:
                raise RuntimeError("execution not found")
            function = session.get(Function, execution.function_id)
            version = session.get(Version, execution.version_id)
            if function is None or version is None:
                raise RuntimeError("function or version no longer exists")
            return _Job(
                command=list(function.command),
                backend=execution.executor_backend,
                version=version,
                hard_timeout_seconds=function.hard_timeout_seconds,
                health_url=function.health_url,
                alive_timeout_seconds=function.alive_timeout_seconds,
            )
        finally:
            session.close()

    def _run(self, job: _Job) -> Outcome:
        if job.backend == HOST:
            return self._run_host(job)
        return self._run_blocking(job)

    def _run_host(self, job: _Job) -> Outcome:
        directory = run_dir.run_dir(self._execution_id)
        code_dir = directory / "code"
        code_dir.mkdir()
        artifact = fetch_decrypt_to_file(job.version)
        try:
            with tarfile.open(artifact, "r:gz") as tar:
                tar.extractall(code_dir, filter="data")
        finally:
            shutil.rmtree(artifact.parent, ignore_errors=True)

        with (
            (directory / "stdout.log").open("ab") as stdout,
            (directory / "stderr.log").open("ab") as stderr,
        ):
            try:
                process = host_process.spawn(job.command, code_dir, stdout, stderr)
            except OSError as exc:
                _ = stderr.write(f"cannot start {job.command[0]!r}: {exc}\n".encode())
                return Outcome("failed", 127)
            self._record_pid(process.pid)
            return host_process.supervise(
                process,
                hard_timeout_seconds=job.hard_timeout_seconds,
                health_url=job.health_url,
                alive_timeout_seconds=job.alive_timeout_seconds,
                health_interval_seconds=settings.health_check_interval_seconds,
                grace_seconds=settings.stop_grace_seconds,
                should_stop=self._should_stop,
            )

    def _run_blocking(self, job: _Job) -> Outcome:
        """Run-to-completion backends (docker): hard timeout only, no health or stop."""
        directory = run_dir.run_dir(self._execution_id)
        artifact = fetch_decrypt_to_file(job.version)
        try:
            result = EXECUTORS[job.backend].run(
                artifact, job.version, job.command, job.hard_timeout_seconds
            )
        finally:
            shutil.rmtree(artifact.parent, ignore_errors=True)
        _ = (directory / "stdout.log").write_text(result.stdout)
        _ = (directory / "stderr.log").write_text(result.stderr)
        if result.exit_code == host_process.TIMEOUT_EXIT_CODE:
            return Outcome("timeout", result.exit_code)
        return Outcome("success" if result.exit_code == 0 else "failed", result.exit_code)

    def _should_stop(self) -> bool:
        if self._signalled:
            return True
        now = time.monotonic()
        if now >= self._next_beat:
            self._next_beat = now + settings.supervisor_heartbeat_seconds
            self._stop_requested = self._beat() or self._stop_requested
        return self._stop_requested

    def _beat(self) -> bool:
        """Heartbeat; returns whether a stop was requested. DB blips are tolerated."""
        try:
            session = session_factory(self._tenant_id)
            try:
                execution = session.get(Execution, self._execution_id)
                if execution is None:
                    return True
                execution.heartbeat_at = utcnow()
                stop = execution.stop_requested
                session.commit()
                return stop
            finally:
                session.close()
        except Exception:
            logger.exception("heartbeat failed for execution %s", self._execution_id)
            return False

    def _record_pid(self, pid: int) -> None:
        session = session_factory(self._tenant_id)
        try:
            execution = session.get(Execution, self._execution_id)
            if execution is not None:
                execution.pid = pid
                session.commit()
        finally:
            session.close()

    def _append_stderr(self, text: str) -> None:
        path = run_dir.run_dir(self._execution_id) / "stderr.log"
        with path.open("ab") as stream:
            _ = stream.write(text.encode())

    def _finish(self, outcome: Outcome) -> None:
        """Persist the result, then drop runtime state; on DB failure the run dir stays
        so the dispatcher's reconciliation can still recover the logs."""
        stdout, stderr = run_dir.read_logs(self._execution_id)
        session = session_factory(self._tenant_id)
        try:
            execution = session.get(Execution, self._execution_id)
            if execution is not None:
                execution.status = outcome.status
                execution.exit_code = outcome.exit_code
                execution.stdout = stdout
                execution.stderr = stderr
                execution.finished_at = utcnow()
                execution.duration_seconds = time.monotonic() - self._started
                session.commit()
        finally:
            session.close()
        run_dir.remove(self._execution_id)


def main(argv: list[str]) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    tenant_id, execution_id = uuid.UUID(argv[0]), uuid.UUID(argv[1])
    return Supervisor(tenant_id, execution_id).run()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

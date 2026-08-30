import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import override

import docker
import requests

from dxforge.db.models import Version
from dxforge.executor.base import ExecutionResult, Executor

RUNTIME_IMAGES = {
    "python-3.11": "python:3.11-slim",
    "node-20": "node:20-slim",
}


class DockerExecutor(Executor):
    @override
    def run(
        self, artifact: Path, version: Version, command: list[str], timeout_seconds: int
    ) -> ExecutionResult:
        client = docker.from_env()
        code_dir: Path | None = None
        container = None
        started = time.monotonic()
        try:
            if version.build_tool == "docker":
                with artifact.open("rb") as stream:
                    images = client.images.load(stream)
                image = images[0].id
                assert image is not None, "loaded image has no id"
                run_command = None
                volumes = None
                working_dir = None
            else:
                code_dir = Path(tempfile.mkdtemp(prefix="dxforge-code-"))
                with tarfile.open(artifact, "r:gz") as tar:
                    tar.extractall(code_dir, filter="data")
                for path in code_dir.rglob("*"):
                    path.chmod(0o755 if path.is_dir() else 0o644)
                try:
                    image = RUNTIME_IMAGES[version.runtime]
                except KeyError as exc:
                    raise ValueError(
                        f"no image for runtime {version.runtime!r}"
                    ) from exc
                run_command = command
                volumes = {str(code_dir): {"bind": "/code", "mode": "ro,z"}}
                working_dir = "/code"

            container = client.containers.run(
                image,
                command=run_command,
                working_dir=working_dir,
                volumes=volumes,
                detach=True,
                cap_drop=["ALL"],
                security_opt=["no-new-privileges"],
                network_mode="none",
                user="1000:1000",
                read_only=True,
                tmpfs={"/tmp": "rw,noexec,nosuid,size=64m"},
            )
            try:
                exit_code = int(container.wait(timeout=timeout_seconds)["StatusCode"])
            except (
                requests.exceptions.ReadTimeout,
                requests.exceptions.ConnectionError,
            ):
                container.kill()
                try:
                    container.wait(timeout=10)
                except (
                    requests.exceptions.ReadTimeout,
                    requests.exceptions.ConnectionError,
                ):
                    pass
                exit_code = 124
            stdout = container.logs(stdout=True, stderr=False) or b""
            stderr = container.logs(stdout=False, stderr=True) or b""
            return ExecutionResult(
                exit_code=exit_code,
                stdout=stdout.decode(errors="replace"),
                stderr=stderr.decode(errors="replace"),
                duration_seconds=time.monotonic() - started,
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass
            if code_dir is not None:
                shutil.rmtree(code_dir, ignore_errors=True)

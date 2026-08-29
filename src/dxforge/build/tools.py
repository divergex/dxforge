import subprocess
import tarfile
import uuid
from pathlib import Path
from typing import override

import docker


class BuildTool:
    name: str = "none"

    def build(self, _source_dir: Path, _command: str | None) -> Path:
        raise NotImplementedError


class NoneTool(BuildTool):
    name = "none"

    @override
    def build(self, source_dir: Path, command: str | None) -> Path:
        return _tar_gz(source_dir)


class MakeTool(BuildTool):
    name = "make"

    @override
    def build(self, source_dir: Path, command: str | None) -> Path:
        invocation = ["make"] + (command.split() if command else [])
        _ = subprocess.run(invocation, cwd=source_dir, check=True)
        return _tar_gz(source_dir)


class DockerTool(BuildTool):
    name = "docker"

    @override
    def build(self, source_dir: Path, command: str | None) -> Path:
        client = docker.from_env()
        tag = f"dxforge-build-{uuid.uuid4().hex[:12]}"
        image, _ = client.images.build(
            path=str(source_dir), dockerfile=command or "Dockerfile", tag=tag
        )
        try:
            artifact = Path(f"{tag}.tar")
            with artifact.open("wb") as out:
                for chunk in image.save():
                    out.write(chunk)
            return artifact
        finally:
            client.images.remove(tag, force=True)


def _tar_gz(source_dir: Path) -> Path:
    artifact = Path(f"{source_dir.name}.tar.gz")
    with tarfile.open(artifact, "w:gz") as tar:
        for entry in sorted(source_dir.iterdir()):
            tar.add(entry, arcname=entry.name)
    return artifact


TOOLS: dict[str, BuildTool] = {
    tool.name: tool for tool in (NoneTool(), MakeTool(), DockerTool())
}

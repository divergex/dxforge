from dataclasses import dataclass
from pathlib import Path

from dxforge.db.models import Version


@dataclass
class ExecutionResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float


class Executor:
    def run(
        self, _artifact: Path, _version: Version, command: list[str], _timeout_seconds: int
    ) -> ExecutionResult:
        raise NotImplementedError
from dxforge.executor.base import Executor
from dxforge.executor.docker_executor import DockerExecutor

HOST = "host"

# Run-to-completion backends. "host" is not here: host processes are long-lived and
# watched by the supervisor (see executor/host_process.py and executor/supervisor.py).
EXECUTORS: dict[str, Executor] = {
    "docker": DockerExecutor(),
}

BACKENDS = (HOST, *EXECUTORS)

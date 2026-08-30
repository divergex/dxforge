from dxforge.executor.base import Executor
from dxforge.executor.docker_executor import DockerExecutor
from dxforge.executor.host_executor import HostExecutor

EXECUTORS: dict[str, Executor] = {
    "docker": DockerExecutor(),
    "host": HostExecutor(),
}

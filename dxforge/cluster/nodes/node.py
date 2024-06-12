from dataclasses import dataclass
from typing import Dict

from docker import DockerClient
from docker.models.containers import Container


@dataclass
class NodeConfig:
    tag: str


class Node:
    def __init__(self, config: NodeConfig = None, docker_client: DockerClient = None):
        self.config = config
        self.docker_client = docker_client
        self.containers: Dict[str, Container] = {}

    def __getitem__(self, item) -> Container:
        return self.containers[item]

    def _get(self, container_id: str = None) -> Container:
        return self.docker_client.containers.get(container_id)

    def log(self, container_id: str = None, **kwargs):
        if container := self._get(container_id):
            return container.logs(**kwargs)

    def build(self):
        self.docker_client.images.build(
            path='..',
            tag=self.config.tag
        )

    def create(self, **kwargs) -> str:
        container = self.docker_client.containers.create(
            self.config.tag,
            **kwargs
        )
        self.containers[container.id] = container
        return container.id

    def start(self, container_id: str = None, **kwargs):
        if container := self._get(container_id):
            container.start(**kwargs)

    def exec(self, container_id: str = None, **kwargs):
        if container := self._get(container_id):
            return container.exec_run(detach=True, **kwargs)

    def stop(self, container_id: str = None, **kwargs):
        if container := self._get(container_id):
            container.stop(**kwargs)

    def remove(self, container_id: str = None, **kwargs):
        if container := self._get(container_id):
            container.remove(**kwargs)
            del self.containers[container_id]

    def status(self, container_id: str = None):
        if container := self._get(container_id):
            return container.status

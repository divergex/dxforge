from dataclasses import dataclass
from typing import Dict

import yaml
from docker import DockerClient
from docker.models.containers import Container


@dataclass
class NodeConfig:
    def __init__(self,
                 tag: str,
                 name: str = None,
                 env: Dict = None,
                 network: str = "bridge",
                 *args, **kwargs):
        self.tag = tag
        self.name = name
        self.env = env
        self.network = network

        if not isinstance(self.env, dict):
            raise TypeError("Environment must be a dictionary")

    @classmethod
    def safe_load(cls, path: str):
        with open(path) as f:
            return cls(**yaml.safe_load(f))


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

    def build(self, path: str = None):
        self.docker_client.images.build(
            path=path,
            tag=self.config.tag
        )

    def create(self, **kwargs) -> str:
        container = self.docker_client.containers.create(
            self.config.tag,
            environment=self.config.env,
            network=self.config.network,
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

    @classmethod
    def from_config(cls, path: str, docker_client: DockerClient = None):
        try:
            config = NodeConfig.safe_load(path)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found at {path}")
        except TypeError as e:
            raise TypeError(f"Invalid config fields. {e}")
        return cls(config, docker_client)

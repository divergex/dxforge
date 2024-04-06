from typing import Dict, Tuple, Union
from uuid import uuid4

import httpx
from docker import DockerClient
from docker.models.images import Image

from .instance import Instance
from .node_config import NodeConfig


class Node:
    def __init__(self, config: NodeConfig):
        self._config = config
        self.instances: Dict[str, Instance] = {}

    @classmethod
    def from_dict(cls,
                  config: dict = None,
                  path=None,
                  info=None) -> 'Node':
        return cls(NodeConfig.from_config(config, path, info))

    @property
    def alive(self):
        return len(self.instances) > 0 and any(instance.alive for instance in self.instances.values())

    @property
    def client(self):
        return httpx.AsyncClient()

    @property
    def config(self) -> NodeConfig:
        return self._config

    @property
    def tag(self):
        return self._config.build.tag

    @property
    def info(self):
        return self._config.info

    @property
    def status(self):
        return {
            "instances": {uuid: instance.ip for uuid, instance in self.instances.items()},
        }

    def create_instance(self, uuid: str = None):
        if uuid is None:
            uuid = uuid4()
        self.instances[uuid] = Instance(self._config)

        return uuid

    def _run(self, func, *args, **kwargs):
        status = {}
        for uuid, instance in self.instances.items():
            try:
                func(instance, *args, **kwargs)
                status[str(uuid)] = {
                    "status": "success"
                }
            except Exception as e:
                status[str(uuid)] = {
                    "status": "error",
                    "error": str(e)
                }
        return status

    def build(self, docker_client: DockerClient, *args, **kwargs) -> Tuple[dict, Union[Image, None]]:
        try:
            image = docker_client.images.build(
                path=self._config.path,
                tag=self._config.build.tag,
                *args, **kwargs
            )

            return {
                "status": "success",
            }, image
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }, None

    def start(self, docker_client: DockerClient) -> dict:
        return self._run(Instance.start, docker_client)

    def stop(self) -> dict:
        return self._run(Instance.stop)

    def log(self, uuid):
        return self.instances[uuid].logs()

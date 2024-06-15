from typing import Dict

import yaml
from docker import DockerClient
from docker.models.services import Service
from docker.types import EndpointSpec, ServiceMode


class Node:
    def __init__(self,
                 docker_client: DockerClient,
                 tag: str,
                 name: str = None,
                 env: Dict = None,
                 network: str = "bridge",
                 *args, **kwargs):
        if not isinstance(env, dict):
            raise TypeError("Environment must be a dictionary")

        self.tag = tag
        self.name = name
        self.env = env
        self.network = network
        self.docker_client = docker_client

        self.instances: Dict[str, Service] = {}

    @property
    def image(self):
        return self.tag

    def _get(self, service_id: str = None) -> Service:
        return self.docker_client.services.get(service_id)

    # gets
    def log(self, service_id: str = None, **kwargs):
        if service := self._get(service_id):
            return service.logs(**kwargs)

    def build(self, path: str = None):
        self.docker_client.images.build(
            path=path,
            tag=self.tag,
            forcerm=True,
            nocache=True,
        )

        dangling_images = self.docker_client.images.list(filters={"dangling": True})

        for image in dangling_images:
            self.docker_client.images.remove(image.id)

    def create(self, **kwargs) -> Service:
        ports = kwargs.get('ports', {})
        replicas = kwargs.get('replicas', 1)
        service = self.docker_client.services.create(
            image=self.image,
            name='feed',
            endpoint_spec=EndpointSpec(ports=ports),
            mode=ServiceMode('replicated', replicas=replicas),
            env=self.env
        )
        self.instances[service.id] = service
        return service

    def stop(self, service_id: str = None):
        if service := self._get(service_id):
            service.remove()
            del self.instances[service_id]

    def status(self, service_id: str = None):
        if service := self._get(service_id):
            return service.attrs['Spec']['Mode']['Replicated']['Replicas']

    @classmethod
    def from_file(cls, path: str, docker_client: DockerClient = None):
        try:
            with open(path) as f:
                return cls(**yaml.safe_load(f), docker_client=docker_client)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found at {path}")
        except TypeError as e:
            raise TypeError(f"Invalid config fields. {e}")

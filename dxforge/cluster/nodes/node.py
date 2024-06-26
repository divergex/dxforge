from typing import Dict, List, Union

import yaml
from docker import DockerClient
from docker.errors import NotFound, APIError
from docker.models.services import Service
from docker.types import EndpointSpec, ServiceMode


class Node:
    def __init__(self,
                 docker_client: DockerClient,
                 image: str,
                 name: str = None,
                 env: Dict = None,
                 network: str = "bridge",
                 tags: List[str] = None,
                 *args, **kwargs):
        if not isinstance(env, dict):
            raise TypeError("Environment must be a dictionary")

        self.image = image
        self.name = name
        self.env = env
        self.network = network
        self.tags = tags or []
        self.docker_client = docker_client

        self.instances: Dict[str, Service] = {}

    def __repr__(self):
        return f"<Node: {self.name}>"

    def build(self, path: str = None):
        self.docker_client.images.build(
            path=path,
            tag=self.image,
            forcerm=True,
            nocache=True,
        )

        dangling_images = self.docker_client.images.list(filters={"dangling": True})

        for image in dangling_images:
            self.docker_client.images.remove(image.id)

    def create(self, ports=None, replicas=1, env: Dict = None, **kwargs):
        ports = {int(k): v for k, v in ports.items()} if ports else {}
        # use default env and substitute additional env vars from kwargs
        env = {**self.env, **env}
        try:
            service = self.docker_client.services.create(
                image=self.image,
                name=self.name,
                endpoint_spec=EndpointSpec(ports=ports),
                mode=ServiceMode('replicated', replicas=replicas),
                env=env,
                networks=[self.network],
            )
            self.instances[service.id] = service
        except APIError as e:
            # see if service already exists
            if 'already exists' in str(e):
                print("Service already exists")
                service = self.service
            else:
                raise e
        return service

    @property
    def service(self) -> Union[Service, None]:
        try:
            return self.docker_client.services.get(self.name, None) if self.name else None
        except NotFound:
            return None

    @property
    def service_details(self):
        if service := self.service:
            return service.attrs

    # gets
    def log(self, service_id: str = None, **kwargs):
        if service := self.service:
            return service.logs(**kwargs)

    def remove(self):
        if service := self.service:
            service.remove()

    def status(self, service_id: str = None):
        if service := self.service:
            return service.attrs['Spec']['Mode']['Replicated']['Replicas'][0]['CurrentTasks'][0]['Status']['State']['Running']

    @classmethod
    def from_file(cls, path: str, docker_client: DockerClient = None):
        try:
            with open(path) as f:
                return cls(**yaml.safe_load(f), docker_client=docker_client)
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found at {path}")
        except TypeError as e:
            raise TypeError(f"Invalid config fields. {e}")

    @classmethod
    def from_service(cls, service: Service):
        env = {}

        for e in service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Env']:
            k, v = e.split('=')
            env[k] = v

        network = service.attrs['Spec']['Networks'][0]['Target'] if service.attrs['Spec'].get('Networks') else "bridge"

        return cls(
            docker_client=service.client,
            image=service.attrs['Spec']['TaskTemplate']['ContainerSpec']['Image'],
            name=service.name,
            env=env,
            network=network
        )

    def to_dict(self):
        return {
            'name': self.name,
            'image': self.image,
            'env': self.env,
            'network': self.network,
            'tags': self.tags
        }

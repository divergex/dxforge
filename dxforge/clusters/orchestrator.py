import asyncio
from typing import Dict

import docker

from .controller import Controller


class Orchestrator:
    def __init__(self, controllers: Dict[str, Controller], docker_client: docker.DockerClient):
        self.controllers = controllers
        self.docker_client = docker_client

    @property
    def status(self):
        return {
            "controllers": {controller: self.controllers[controller].status for controller in self.controllers},
        }

    @property
    def info(self):
        return {
            "controllers": {controller: self.controllers[controller].info for controller in self.controllers},
        }

    @staticmethod
    async def stop_containers(container):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, container.stop)

    async def stop(self):
        await asyncio.gather(
            *[self.stop_containers(container) for container in self.docker_client.containers.list()]
        )
        self.docker_client.close()

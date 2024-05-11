import asyncio
from typing import Dict

import docker

from .controller import Controller


class Orchestrator:
    def __init__(self, controllers: Dict[str, Controller], docker_client: docker.DockerClient):
        self.controllers = controllers
        self.docker_client = docker_client

    def status(self):
        status = {
            controller_name: {
                "stopped": [],
                "running": []
            }
            for controller_name in self.controllers
        }
        for controller in self.controllers:
            for node in self.controllers[controller].nodes:
                if self.controllers[controller].nodes[node].alive:
                    status[controller]["running"].append(node)
                else:
                    status[controller]["stopped"].append(node)
        return status

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

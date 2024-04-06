from typing import List

import docker
import httpx
from docker.errors import APIError

from .clusters import Orchestrator, Controller
from .utils import SingletonMeta


class Forge(metaclass=SingletonMeta):
    def __init__(self,
                 orchestrators: List[Orchestrator] = None):
        self._orchestrators = orchestrators

    @classmethod
    def from_config(cls, config: dict) -> 'Forge':
        network_name = 'dxforge'
        network_params = {
            'driver': 'bridge',
            'name': network_name
        }

        docker_client = docker.DockerClient(base_url='unix://var/run/docker.sock') if docker else None

        try:
            docker_client.networks.create(**network_params)
        except APIError:
            pass

        controllers = {}

        for name, path in config.get("controllers", {}).items():
            controllers[name] = Controller.from_file(path, docker_client)
        orchestrator = Orchestrator(controllers, docker_client)

        return cls([orchestrator])

    @property
    def client(self):
        return httpx.AsyncClient()

    @property
    def orchestrator(self):
        return self._orchestrators[0]

    async def stop(self):
        try:
            self._orchestrators[0].docker_client.networks.get("dxforge").remove()
        except APIError:
            pass
        await self._orchestrators[0].stop()

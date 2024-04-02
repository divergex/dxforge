from docker import DockerClient
from docker.models.containers import Container
from docker.models.images import Image

from .node_config import NodeConfig


class Instance:
    def __init__(self,
                 data: NodeConfig = None,
                 ):
        self.data = data
        self._container: Container | None = None
        self._image: Image | None = None

    @property
    def status(self):
        return self._container.status

    @property
    def ip(self):
        if self._container:
            if self.data.run.network == "host":
                return "localhost"
            elif self.data.run.network == "bridge":
                return self._container.attrs["NetworkSettings"]["IPAddress"]
            else:
                return self._container.attrs["NetworkSettings"]["Networks"][self.data.run.network]["IPAddress"]

        return None

    def create(self, docker_client: DockerClient) -> Container:
        self._container = docker_client.containers.create(
            image=self.data.build.tag,
            ports=self.data.run.ports,
            network=self.data.run.network if self.data.run.network != "host" else None,
            detach=True,
            host_config=docker_client.create_host_config(extra_hosts={'host.docker.internal': 'host-gateway'})

        )
        return self._container

    def start(self, docker_client: DockerClient):
        if not self._container:
            self.create(docker_client)
        self._container.start()
        self._container.reload()

    def stop(self):
        if self._container:
            self._container.stop()
            self._container.remove()
            self._container = None

    def logs(self):
        if self._container:
            return self._container.logs()
        return None

    @property
    def info(self):
        return {
            "ip": self.ip,
            "ports": self.data.run.ports,
            "network": self.data.run.network,
        }

import uuid
from pathlib import Path
from dataclasses import dataclass

import docker
from docker.models.containers import Container

from dxlib.interfaces import Service, HttpEndpoint


@dataclass
class ContainerStart:
    port: int
    identifier: str = None


class Orchestrator(Service):
    def __init__(self, project_name: str, project_dir: str, service_id, network_name="divergex", daemon=False):
        super().__init__(project_name, service_id)
        self.project_name = project_name
        self.network_name = network_name
        self.project_dir = Path(project_dir).resolve()

        self.client = docker.from_env()
        self._create_network()
        self.daemon = daemon
        self.strategies: set = set()

    def _create_network(self):
        """Create a Docker network for the project if it doesn't already exist."""
        try:
            self.client.networks.get(self.network_name)
        except docker.errors.NotFound:
            self.client.networks.create(self.network_name, driver="bridge")
            print(f"Created Docker network: {self.network_name}")

    def list_images(self):
        """List all images matching the strategy naming pattern."""
        images = self.client.images.list()
        return [image.tags for image in images if image.tags]

    def build_image(self, strategy_name: str):
        """Build a Docker image for a strategy."""
        strategy_path = self.project_dir / strategy_name
        if not strategy_path.exists():
            raise FileNotFoundError(f"Strategy {strategy_name} not found in {self.project_dir}")

        dockerfile = strategy_path / "Dockerfile.template"
        if not dockerfile.exists():
            raise FileNotFoundError(f"Dockerfile.template not found in {self.project_dir}")

        image_tag = f"{self.project_name}_{strategy_name.lower()}"
        self.client.images.build(
            path=str(strategy_path),
            dockerfile=str(dockerfile),
            tag=image_tag
        )
        print(f"Built Docker image for strategy: {strategy_name}")

    @HttpEndpoint.get("/dxforge/list")
    def list_containers(self):
        """List all running and stopped containers for strategies."""
        containers = self.client.containers.list(all=True)
        strategy_containers = [
            {
                "name": container.name,
                "id": container.id,
                "image": container.image.tags[0] if container.image.tags else "unknown",
                "status": container.status,
                "ports": container.ports,
            }
            for container in containers
            if container.name.startswith(f"{self.project_name}_")
        ]
        return strategy_containers

    @HttpEndpoint.get("/dxforge/list/{strategy_name}")
    def list_containers_by_strategy(self, strategy_name: str):
        """List all running and stopped containers for a specific strategy."""
        containers = self.list_containers()
        return [container for container in containers if
                container["name"].startswith(f"{self.project_name}_{strategy_name.lower()}")]

    @HttpEndpoint.post("/dxforge/stop/{strategy_name}")
    def stop_all(self, strategy_name: str):
        containers = self.list_containers()
        for container in containers:
            if container["name"].startswith(f"{self.project_name}_{strategy_name.lower()}"):
                self.stop_container(strategy_name, container["name"].split("_")[-1])

    @HttpEndpoint.post("/dxforge/start/{strategy_name}")
    def _start_container(self, strategy_name: str, start: ContainerStart):
        container, identifier = self.start_container(strategy_name, start.port, start.identifier)
        return container.name, identifier

    def start_container(self, strategy_name: str, port: int, identifier: str = None) -> (
            Container, str):
        """Start a new container for the given strategy."""
        instance_identifier = identifier or uuid.uuid4()
        image_tag = f"{self.project_name}_{strategy_name.lower()}"
        try:
            image = self.client.images.get(image_tag)
            if not image or not image.id:
                raise ValueError(f"Image for strategy {strategy_name} not found. Please build it first.")
        except docker.errors.ImageNotFound:
            raise ValueError(f"Image for strategy {strategy_name} not found. Please build it first.")

        container_name = f"{self.project_name}_{strategy_name.lower()}_{instance_identifier}"

        # port should only be accessible with container:port, and not open on host (to avoid conflicts)
        container = self.client.containers.run(
            image.id,
            detach=True,
            ports={f"{port}/tcp": None},
            name=container_name,
            network=self.network_name,
        )
        self.strategies.add(strategy_name)
        print(f"Started container {container_name} for {strategy_name} on port {port}")
        return container, instance_identifier

    @HttpEndpoint.get("/dxforge/status/{strategy_name}/{instance_id}")
    def status(self, strategy_name: str, instance_id: str):
        containers = self.list_containers()
        container_name = f"{self.project_name}_{strategy_name.lower()}_{instance_id}"
        for container in containers:
            if container["name"] == container_name:
                return container["status"]
        return "Not found"

    def stop_container(self, strategy_name: str, instance_id: str):
        """Stop a running container by name."""
        try:
            container = self.client.containers.get(f"{self.project_name}_{strategy_name.lower()}_{instance_id}")
            container.stop()
            print(f"Stopped container: {strategy_name}")
        except docker.errors.NotFound:
            print(f"Container {strategy_name} not found.")

    def cleanup(self):
        """Remove all stopped containers (that are part of the project) and dangling images."""
        containers = self.client.containers.list(all=True)
        for container in containers:
            if container.status == "exited" and container.name.startswith(f"{self.project_name}_"):
                print(f"Removing container: {container.name}")
                container.remove()

        # Remove dangling images
        self.client.images.prune()
        print("Cleaned up dangling images.")

    def stop(self):
        if not self.daemon:
            for strategy in self.strategies:
                self.stop_all(strategy)
            self.cleanup()
            self.client.close()
            print("Closed Docker client.")

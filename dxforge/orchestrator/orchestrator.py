import logging
import uuid
import asyncio
from pathlib import Path
from dataclasses import dataclass

import docker
from docker.errors import NotFound
from dxlib.network.servers import HttpEndpoint
from fastapi import APIRouter, UploadFile, File

from dxlib.network.services import Service

from dxforge.manager import create


@dataclass
class ContainerStart:
    port: int
    identifier: str = None


class Orchestrator(Service):
    def __init__(self,
                 project_name: str,
                 project_dir: str,
                 service_id,
                 router=None,
                 daemon=False
                 ):
        super().__init__(project_name, service_id)
        self.project_name = project_name
        self.project_dir = Path(project_dir).resolve()

        self.client = docker.from_env()
        self.daemon = daemon
        self.services: set = set()

        self.manager = create()

        self.fastapi_router = router or APIRouter()
        self.logger = logging.getLogger(__name__)


    @HttpEndpoint.get("/list")
    async def list_images(self):
        """List all images matching the strategy naming pattern."""
        images = self.client.images.list()
        return [{
            "id": image.id,
            "tags": image.tags,
            "attrs": image.attrs,
        } for image in images if image.tags]

    @HttpEndpoint.post("/create")
    # should receive an uploaded .py file
    async def create_service(self, service_name: str, file: UploadFile = File(...)):
        content = await file.read()
        tag = self.manager.package(service_name, self.client, content.decode("utf-8"))
        return tag

    @HttpEndpoint.post("/build")
    async def build_image(self, service_name: str, service_tag: str = None):
        """Build a Docker image for an existing service Dockerfile."""
        service_path = self.project_dir / service_name
        if not service_path.exists():
            raise FileNotFoundError(f"Directory not found for {service_name} in {self.project_dir}")

        dockerfile = service_path / "Dockerfile"
        if not dockerfile.exists():
            raise FileNotFoundError(f"Dockerfile not found in {self.project_dir}")

        image_tag = service_tag or f"{self.project_name}_{service_name.lower()}"
        self.client.images.build(
            path=str(image_tag),
            dockerfile=str(dockerfile),
            tag=image_tag
        )
        print(f"Built Docker image: {image_tag}")

    @HttpEndpoint.get("/start")
    async def list_containers(self):
        """List all running and stopped containers for services."""
        containers = self.client.containers.list(all=True)
        service_containers = [
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
        return service_containers

    async def list_containers_by_service(self, service_name: str):
        """List all running and stopped containers for a specific service."""
        containers = await self.list_containers()
        return [container for container in containers if
                container["name"].startswith(f"{self.project_name}_{service_name.lower()}")]

    async def stop_all(self, service_name: str):
        containers = await self.list_containers()
        for container in containers:
            if container["name"].startswith(f"{self.project_name}_{service_name.lower()}"):
                await self.stop_container(service_name, container["name"].split("_")[-1])

    def _start_container(self, service_name: str, start: ContainerStart):
        container, identifier = self.start_container(service_name, start.port, start.identifier)
        return container.name, identifier

    @HttpEndpoint.post("/start")
    async def start_container(self,
                              service_name: str,
                              port: int,
                              identifier: str = None
                              ):
        """Start a new container for the given service."""
        instance_identifier = identifier or uuid.uuid4()
        image_tag = f"{self.project_name}_{service_name.lower()}"
        try:
            image = self.client.images.get(image_tag)
            if not image or not image.id:
                raise ValueError(f"Image for service {service_name} not found. Please build it first.")
        except docker.errors.ImageNotFound:
            raise ValueError(f"Image for service {service_name} not found. Please build it first.")

        container_name = f"{self.project_name}_{service_name.lower()}_{instance_identifier}"

        # port should only be accessible with container:port, and not open on host (to avoid conflicts)
        container = self.client.containers.run(
            image.id,
            detach=True,
            ports={f"{port}/tcp": None},
            name=container_name,
        )
        self.services.add(service_name)
        print(f"Started container {container_name} for {service_name} on port {port}")
        return instance_identifier.__str__(), container.name

    @HttpEndpoint.get("/status")
    async def status(self, service_name: str, instance_id: str):
        containers = await self.list_containers()
        container_name = f"{self.project_name}_{service_name.lower()}_{instance_id}"
        for container in containers:
            if container["name"] == container_name:
                return container["status"]
        return "Not found"

    @HttpEndpoint.post("/stop")
    async def stop_container(self, service_name: str, instance_id: str):
        """Stop a running container by name."""
        try:
            container = self.client.containers.get(f"{self.project_name}_{service_name.lower()}_{instance_id}")
            container.stop()
            print(f"Stopped container: {service_name}")
        except docker.errors.NotFound:
            print(f"Container {service_name} not found.")

    @HttpEndpoint.post("/cleanup")
    async def cleanup(self):
        """Remove all stopped containers (that are part of the project) and dangling images."""
        containers = self.client.containers.list(all=True)
        for container in containers:
            if container.status == "exited" and container.name.startswith(f"{self.project_name}_"):
                print(f"Removing container: {container.name}")
                container.remove()

        self.client.images.prune()  # Remove dangling
        print("Cleaned up dangling images.")

    def stop(self):
        if not self.daemon:
            for service in self.services:
                self.stop_all(service)
            # run cleanup async on loop
            asyncio.run(self.cleanup())
            self.client.close()
            print("Closed Docker client.")

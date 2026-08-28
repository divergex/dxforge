import docker

from orchestrator.db import ContainerStore


class ContainerRuntime:
    """
    Handles Docker operations for containers and updates ContainerStore.
    """
    def __init__(self, store: ContainerStore):
        self.client = docker.from_env()
        self.store = store

    def start(self, project_id: str, container_id: str, image: str, **kwargs):
        container = self.client.containers.run(image, detach=True, name=container_id, **kwargs)
        self.store.update_status(project_id, container_id, "running")
        return container

    def stop(self, project_id: str, container_id: str, timeout: int = 10):
        container = self.client.containers.get(container_id)
        container.stop(timeout=timeout)
        self.store.update_status(project_id, container_id, "stopped")

    def remove(self, project_id: str, container_id: str, force: bool = False):
        container = self.client.containers.get(container_id)
        container.remove(force=force)
        self.store.delete_container(project_id, container_id)

    def inspect(self, container_id: str):
        container = self.client.containers.get(container_id)
        return container.attrs

    def restart(self, project_id: str, container_id: str):
        container = self.client.containers.get(container_id)
        container.restart()
        self.store.update_status(project_id, container_id, "running")

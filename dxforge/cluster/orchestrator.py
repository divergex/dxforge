from typing import Dict

from docker import DockerClient

from .nodes import NodeGroup


class Orchestrator:
    def __init__(self, docker_client: DockerClient):
        self.docker_client = docker_client
        self.node_groups: Dict[str, NodeGroup] = {}

    def add_group(self, name: str, node_group: NodeGroup):
        self.node_groups[name] = node_group

    def remove_group(self, name: str):
        del self.node_groups[name]

    def get_group(self, name: str) -> NodeGroup:
        return self.node_groups[name]

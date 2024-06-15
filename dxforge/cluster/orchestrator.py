from typing import Dict

from docker import DockerClient
from .nodes import Node


class Orchestrator:
    def __init__(self, docker_client: DockerClient):
        self.docker_client = docker_client
        self.nodes = {}

    def new(self, name: str, tag: str, env: Dict = None, network: str = "bridge") -> Node:
        node = Node(self.docker_client, tag, name, env, network)
        return self.add(node)

    def add(self, node: Node) -> Node:
        self.nodes[node.name] = node
        return node

    def remove(self, name: str):
        del self.nodes[name]

    def get(self, name: str) -> Node:
        return self.nodes[name]

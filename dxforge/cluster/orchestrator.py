from typing import Dict

from docker import DockerClient

from .nodes import Node
from .registry import Registry


class NodeRegistry(Registry):
    def __init__(self):
        super().__init__()
        self._registry: Dict[str, Node] = {}


class Orchestrator:
    def __init__(self, docker_client: DockerClient):
        self.docker_client = docker_client
        self.nodes = NodeRegistry()

    def new(self, name: str, tag: str, env: Dict = None, network: str = "bridge") -> Node:
        node = Node(self.docker_client, tag, name, env, network)
        return self.add(node)

    def add(self, node: Node) -> Node:
        self.nodes.register(node.name, node)
        return node

    def remove(self, name: str):
        self.nodes.remove(name)

    def get(self, name: str) -> Node:
        return self.nodes.get(name)

from typing import Dict

from docker import DockerClient

from .nodes import Node
from .registry import Registry


class NodeRegistry(Registry):
    def __init__(self):
        super().__init__()
        self._registry: Dict[str, Node] = {}

    def remove(self, name: str):
        node = self.get(name)
        node.remove()

        for tag in node.tags:
            self._tags[tag].remove(name)

        del self._registry[name]


class Orchestrator:
    def __init__(self, docker_client: DockerClient):
        self.docker_client = docker_client
        self._nodes = NodeRegistry()

    def new(self, name: str, tag: str, env: Dict = None, network: str = "bridge") -> Node:
        node = Node(self.docker_client, tag, name, env, network)
        return self.add(node)

    def add(self, node: Node) -> Node:
        self._nodes.register(node.name, node)
        return node

    def remove(self, name: str):
        self._nodes.remove(name)

    def get(self, name: str) -> Node:
        return self._nodes.get(name)

    def load(self):
        for service in self.docker_client.services.list():
            node = Node.from_service(service)
            self.add(node)

    def clean(self):
        self._nodes.clear()

    def find_all(self, tags):
        return self._nodes.find_all(tags)

    @property
    def nodes(self):
        return self._nodes.all()

from dataclasses import dataclass
from typing import Dict


from .node import Node


@dataclass
class NodeGroup:
    def __init__(self, nodes: Dict[str, Node]):
        self.nodes = nodes

    def __getitem__(self, item) -> Node:
        return self.nodes[item]

    def from_config(self, config: Dict[str, NodeConfig], docker_client: DockerClient):
        for name, node_config in config.items():
            self.nodes[name] = Node(node_config, docker_client)
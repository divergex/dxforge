from __future__ import annotations

import logging
import os

from docker import DockerClient
from docker.errors import ImageNotFound
import yaml

from .node import Node


class Controller:
    def __init__(self, docker_client: DockerClient):
        self._nodes: dict[str, Node] = {}
        self.docker_client = docker_client
        self.logger = logging.Logger(__name__)

    @classmethod
    def from_file(cls, config_path: str, docker_client: DockerClient):
        config = yaml.safe_load(open(config_path, "r"))["controller"]
        root_path = config.get("path", None)
        nodes = config.get("nodes", {})

        controller = cls(docker_client)
        for node_name, setup in nodes.items():
            try:
                node_path = os.path.join(root_path, setup["path"])
                node_config = yaml.safe_load(open(os.path.join(str(node_path), setup["config"]), "r"))

                if setup.get("info", None):
                    node_info = yaml.safe_load(open(os.path.join(str(node_path), setup["info"]), "r"))
                else:
                    node_info = None

                if node := Node.from_dict(node_config, node_path, node_info):
                    controller.nodes[node_name] = node
            except ImageNotFound:
                continue

        return controller

    @property
    def nodes(self) -> dict[str, Node]:
        return self._nodes

    def build_node(self, node: Node, *args, **kwargs) -> dict:
        for depend_node_tag in node.config.build.depends_on:
            depend_node_name = depend_node_tag.split(":")[0]
            depend_node = self.nodes[depend_node_name]
            self.build_node(depend_node)
        response, _ = node.build(self.docker_client, *args, **kwargs)
        return response

    def start_node(self, node: Node) -> dict:
        return node.start(self.docker_client)

    @staticmethod
    def stop_node(node: Node) -> dict:
        return node.stop()

    def status(self):
        status = {
            "nodes": {
                node_name: node.status for node_name, node in self.nodes.items()
            },
            "docker-client-containers": {
                container.name: container.status for container in self.docker_client.containers.list()
            }
        }

        return status

    @property
    def info(self):
        return {
            "nodes": {node_name: node.info for node_name, node in self.nodes.items()},
        }

    def stop(self):
        for node in self.nodes.values():
            self.stop_node(node)

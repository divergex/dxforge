import unittest

from docker import DockerClient

from cluster.nodes.node import NodeConfig, Node


class TestNode(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tag = 'python:3.9-alpine'
        cls.tag = tag
        cls.config = NodeConfig(tag=tag)
        client = DockerClient()
        client.images.pull(tag)
        cls.client = client

    def test_create(self):
        self.assertEqual(self.config.tag, self.tag)

        node = Node(self.config, self.client)

        node_id = node.create()

        self.assertTrue(node.containers)
        self.assertIn(node[node_id].status, ['created'])

        node.remove(node_id)

    def test_start(self):
        node = Node(self.config, DockerClient())

        node_id = node.create(command="/bin/sh -c 'while true; do sleep 1; done'", tty=True, stdin_open=True)
        node.start(node_id)

        node.log(node_id, stream=True)

        self.assertIn(node.status(node_id), ['running'])

        node.remove(node_id, force=True)


if __name__ == '__main__':
    unittest.main()

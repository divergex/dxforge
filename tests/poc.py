import os
import time

from docker import DockerClient
from dxforge.cluster import Node


def main():
    docker_client = DockerClient()
    node = Node.from_config('../template/strategies/strategy.yaml', docker_client)

    node.build('../template/strategies')
    ports = {node.config.env['PORT']: node.config.env['PORT']}
    node_id = node.create(ports=ports)

    def clear():
        os.system('clear')

    try:
        node.start(node_id)

        while node.status(node_id) != 'running':
            time.sleep(1)

        while True:
            out = node.log(node_id).decode()
            clear()
            print(out)
            # clear stdout
            time.sleep(1)

    except KeyboardInterrupt:
        pass

    finally:
        node.stop(node_id)
        clear()
        out = node.log(node_id).decode()
        print(out)
        node.remove(node_id)


if __name__ == "__main__":
    main()

import time

from cluster import Node
from dxforge import Forge


def main():
    addr = 'docker0'

    forge = Forge("unix:///home/rzimmerdev/.docker/desktop/docker.sock")
    forge.register_swarm(addr)

    folder = "../template/feeds"
    env = {
        'PORT': 5000,
        'HOST': '0.0.0.0',
    }

    # print existing services
    for service in forge.orchestrator.docker_client.services.list():
        print(service)
        node = Node.from_service(service)
        forge.orchestrator.add(node)
    if 'feed' not in forge.orchestrator.nodes:
        node = forge.orchestrator.new("feed", "feeds", env)
        node.build(folder)

        port = int(node.env.get('PORT', 5000))

        print("Creating service...")
        service = node.create(ports={port: port})

        print("Containers:")
        for container in service.tasks():
            print(container)

    else:
        node = forge.orchestrator.nodes['feed']

        # remove service
        service = node.service
        service.remove()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    forge.orchestrator.remove("feeds")


if __name__ == "__main__":
    main()

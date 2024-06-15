import time

from dxforge import Forge


def main():
    addr = 'docker0'

    forge = Forge("unix:///home/rzimmerdev/.docker/desktop/docker.sock")
    forge.register_swarm(advertise_addr=addr)

    folder = "../template/feeds"
    env = {
        'PORT': 5000,
        'HOST': '0.0.0.0',
    }

    node = forge.orchestrator.new("feeds", "feeds", env)
    node.build(folder)

    port = int(node.env.get('PORT', 5000))

    print("Creating service...")
    service = node.create(ports={port: port})

    print("Containers:")
    for container in service.tasks():
        print(container)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

    forge.orchestrator.remove("feeds")
    forge.unregister_swarm()


if __name__ == "__main__":
    main()

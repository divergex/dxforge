import sys

from docker import from_env
from docker.errors import DockerException


def stop(client, name):
    try:
        container = client.containers.get(name)
        container.stop()
        return True
    except DockerException as e:
        return False


if __name__ == "__main__":
    print(
        stop(from_env(), sys.argv[1])
    )

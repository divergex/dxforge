import sys

from docker import from_env
from docker.errors import DockerException


def remove(client, name):
    try:
        container = client.containers.get(name)
        container.remove(force=True)
        return True
    except DockerException as e:
        return False


if __name__ == "__main__":
    print(
        remove(from_env(), sys.argv[1])
    )

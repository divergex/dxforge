import sys

from docker import from_env
from docker.errors import DockerException


def logs(client, name):
    try:
        container = client.containers.get(name)
        return container.logs(stdout=True, stderr=True).decode("utf-8")
    except DockerException as e:
        return None


if __name__ == "__main__":
    print(
        logs(from_env(), sys.argv[1])
    )
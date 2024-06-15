import argparse
import uvicorn

from . import App


def main(docker_socket):
    uvicorn.run(App(docker_socket), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the dxforge app")
    parser.add_argument("--docker-socket", default="unix://var/run/docker.sock")
    args = parser.parse_args()

    main(args.docker_socket)

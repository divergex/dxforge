import signal
import sys

from dxlib.interfaces.services.http.fastapi import FastApiServer
from dxforge.registry.mesh import MeshService


if __name__ == "__main__":
    mesh = MeshService("dxforge", "forge-one")
    server = FastApiServer(host="127.0.0.1", port=7000)
    server.register(mesh)

    signal.signal(signal.SIGINT, lambda signum, frame: sys.exit(0))
    server.run()

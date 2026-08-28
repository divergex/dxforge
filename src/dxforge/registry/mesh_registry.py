import signal
import sys
import threading
import time

from dxlib.interfaces.servers.http.fastapi import FastApiServer

from dxforge.registry.mesh import MeshService, MeshInterface
from dxforge.registry.mesh.mesh_service import ServiceModel

if __name__ == "__main__":
    mesh = MeshService("dxforge", "forge-one")
    server = FastApiServer(host="127.0.0.1", port=5000)
    server.register(mesh)
    mesh_interface = MeshInterface()
    mesh_interface.register(server)

    t = threading.Thread(target=server.run)
    t.start()

    def signal_handler(sig, frame):
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        time.sleep(1)
        service = ServiceModel("MyService", "my-service-1", endpoints="http://localhost:5000", tags=["greeter"])
        mesh_interface.register_service(service)

        print(mesh_interface.search_services("greeter"))

        server.should_exit = True
        t.join()

    except KeyboardInterrupt:
        sys.exit(0)

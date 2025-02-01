from fastapi import APIRouter

from dxlib.interfaces.services.http.fastapi import FastApiServer
from dxlib.interfaces.internal import MeshService

from dxforge.orchestrator import Orchestrator


class Forge:
    def __init__(self, project_name, project_dir, service_id, host, port):
        tags_metadata = [
            {"name": "orchestrator", "description": "Orchestrator operations"},
            {"name": "mesh", "description": "Mesh operations"},
        ]

        self.server = FastApiServer(host, port, openapi_tags=tags_metadata)

        orchestrator_router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])
        mesh_router = APIRouter(prefix="/mesh", tags=["mesh"])
        self.orchestrator = Orchestrator(project_name, project_dir, service_id, orchestrator_router)
        self.controller = MeshService(None, None)

        self.server.register(self.orchestrator)
        self.server.register(self.controller, external_router=mesh_router)

    def run(self):
        try:
            self.server.run()
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()

    def stop(self):
        self.orchestrator.stop()

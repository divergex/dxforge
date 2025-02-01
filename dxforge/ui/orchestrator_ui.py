from fastapi import APIRouter, Request

from dxlib.interfaces import Service

from dxforge.orchestrator import Orchestrator


class OrchestratorUI(Service):
    def __init__(self,
                 orchestrator: Orchestrator,
                 templates,
                 router=None,
                 name=None,
                 service_id=None,
                 ):
        super().__init__(name, service_id)
        self.orchestrator = orchestrator
        self.router = router or APIRouter()
        self.templates = templates
        self._register_routes()

    def _register_routes(self):
        self.router.add_api_route("/", self.index, methods=["GET"])

    async def index(self, request: Request):
        images = await self.orchestrator.list_images()
        containers = await self.orchestrator.list_containers()
        return self.templates.TemplateResponse("orchestrator.html",
                                               {"request": request, "images": images, "containers": containers})

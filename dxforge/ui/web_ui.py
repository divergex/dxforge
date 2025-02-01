from starlette.staticfiles import StaticFiles
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from dxlib.interfaces import Service

from dxforge.ui.orchestrator_ui import OrchestratorUI


class WebUI(Service):
    def __init__(self,
                 name=None,
                 service_id=None,
                 template_dir: str = "dxforge/ui/templates"
                 ):
        super().__init__(name, service_id)
        self.router = APIRouter()
        self.templates = Jinja2Templates(directory=template_dir)

    async def index(self, request: Request):
        return self.templates.TemplateResponse("index.html", {"request": request})

    def register_routes(self, forge):
        orchestrator_router = APIRouter(prefix="/orchestrator")
        orchestrator_ui = OrchestratorUI(forge.orchestrator, self.templates, router=orchestrator_router)

        forge.server.app.mount("/ui/static", StaticFiles(directory="dxforge/ui/static"), name="static")
        forge.server.register(orchestrator_ui)

        self.router.add_api_route("/", self.index, methods=["GET"])
        forge.server.app.include_router(self.router)

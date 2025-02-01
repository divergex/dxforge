from dxlib.interfaces.internal import MeshService
from fastapi import APIRouter

from dxlib.interfaces import Service


class ControlPlane(Service):
    def __init__(self, router=None, name=None, service_id=None):
        super().__init__(name, service_id)
        self.mesh = MeshService(name, service_id)

        self.router = router or APIRouter()
        self._register_routes()

    def _register_routes(self):
        for key, func in self.mesh.__class__.__dict__.items():
            if hasattr(func, "endpoint"):
                endpoint = func.__get__(self.mesh).endpoint
                self.router.add_api_route(
                    endpoint.path,
                    endpoint.func,
                    methods=[endpoint.method],
                    response_model=endpoint.response_model
                )

from dxlib.interfaces.internal import MeshService
from fastapi import APIRouter

from dxlib.interfaces import Service


class MeshController(Service):
    def __init__(self, router=None, name=None, service_id=None):
        super().__init__(name, service_id)

        self.router = router or APIRouter()
from fastapi import FastAPI

from ..forge import Forge


class App(FastAPI):
    def __init__(self, docker_socket=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.forge = Forge(docker_socket)

        from .routes import router
        self.include_router(router)

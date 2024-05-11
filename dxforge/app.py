from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from .forge import Forge


class App(FastAPI):
    def __init__(self, forge: Forge, origins=None, *args, **kwargs):
        from .routers import cluster_router, root_router
        super().__init__(*args, **kwargs)

        self.forge = forge

        if origins is None:
            # any localhost port
            allow_origin_regex = r"http://localhost:\d+"
            origins = "*"

        # noinspection PyTypeChecker
        self.add_middleware(
            middleware_class=CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        self.include_router(cluster_router.router, prefix="/cluster", tags=["cluster"])
        self.include_router(root_router.router, tags=["root"])


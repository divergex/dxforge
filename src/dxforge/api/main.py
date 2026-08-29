import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from dxforge.api.routers import (
    credentials,
    functions,
    health,
    projects,
    tenants,
    upload,
    versions,
)

logger = logging.getLogger(__name__)


def create_app(version: str, api_prefix: str = "/api/v1") -> FastAPI:
    app = FastAPI(title="dxforge", version=version)

    async def _internal_error(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "internal error"})

    app.add_exception_handler(Exception, _internal_error)

    for router in (
        tenants.router,
        projects.router,
        functions.router,
        versions.router,
        upload.router,
        credentials.router,
        health.router,
    ):
        app.include_router(router, prefix=api_prefix)
    return app

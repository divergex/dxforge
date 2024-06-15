from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..forge import Forge

forge = Forge()
router = APIRouter()


@router.get("/status")
async def status():
    return JSONResponse(content={"status": "ok"})


@router.get("/nodes")
async def nodes():
    if forge.orchestrator is None:
        return JSONResponse(content={"nodes": []})
    return JSONResponse(content={"nodes": list(forge.orchestrator.nodes.keys())})

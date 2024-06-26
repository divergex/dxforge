from typing import Optional, List, Dict

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..forge import Forge

forge = Forge()
router = APIRouter()


@router.get("/status")
async def status():
    return JSONResponse(content={"status": "ok"})


class Node(BaseModel):
    name: str
    image: str
    env: Optional[Dict] = {}
    network: Optional[str] = "bridge"
    tags: Optional[List[str]] = []


@router.get("/nodes")
async def get_nodes(tags: Optional[List[str]] = None):
    if forge.orchestrator is None:
        return JSONResponse(content={"nodes": []})
    elif tags:
        return JSONResponse(content={"nodes": list(forge.orchestrator.find_all(tags))})
    else:
        return JSONResponse(content={"nodes": list(forge.orchestrator.nodes)})


@router.get("/nodes/{name}")
async def get_node(name: str):
    if forge.orchestrator is None:
        return JSONResponse(content={"node": None})
    elif name in forge.orchestrator.nodes:
        node = forge.orchestrator.get(name)
        return JSONResponse(content={"node": node.to_dict()})
    else:
        return JSONResponse(content={"node": None})


@router.post("/nodes")
async def create_node(node: Node):
    try:
        node = forge.orchestrator.new(node.name, node.image, node.env, node.network)
        return JSONResponse(content={"node": node.to_dict()})
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


@router.delete("/nodes/{name}")
async def delete_node(name: str):
    try:
        forge.orchestrator.remove(name)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        return JSONResponse(content={"error": str(e)})


@router.get("/nodes/{name}/service")
async def get_service(name: str):
    if forge.orchestrator is None:
        return JSONResponse(content={"service": None})
    elif name in forge.orchestrator.nodes:
        node = forge.orchestrator.get(name)
        return JSONResponse(content={"service": node.service_details})
    else:
        return JSONResponse(content={"service": None})


# start service
@router.post("/nodes/{name}/service")
async def start_service(name: str, body: Dict):
    if forge.orchestrator is None:
        return JSONResponse(content={"service": None})
    elif name in forge.orchestrator.nodes:
        node = forge.orchestrator.get(name)
        service = node.create(**body)
        response = {"id": service.attrs.get('ID', None) if hasattr(service, 'attrs') else None}
        return JSONResponse(content=response)
    else:
        return JSONResponse(content={"service": None})


# remove service
@router.delete("/nodes/{name}/service")
async def remove_service(name: str):
    if forge.orchestrator is None:
        return JSONResponse(content={"status": "ok"})
    elif name in forge.orchestrator.nodes:
        node = forge.orchestrator.get(name)
        node.remove()
        return JSONResponse(content={"status": "ok"})
    else:
        return JSONResponse(content={"status": "ok"})

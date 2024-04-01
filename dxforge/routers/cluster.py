from json import JSONDecodeError

from fastapi import APIRouter, Request, HTTPException

from ..forge import Forge
from ..clusters import Controller, Node

router = APIRouter()
forge = Forge()


def get_controller(controller: str) -> Controller:
    if not (controller := forge.orchestrator.controllers.get(controller, None)):
        raise HTTPException(status_code=404, detail="controller not found")
    return controller


def get_node(controller: Controller, node: str) -> Node:
    if not (node := controller.nodes.get(node, None)):
        raise HTTPException(status_code=404, detail="node not found")
    return node


@router.get("/")
async def get_info():
    return await forge.orchestrator.info


@router.get("/{controller}")
async def get_controller_info(controller: str):
    if not (controller := get_controller(controller)):
        raise HTTPException(status_code=404, detail="controller not found")

    return await controller.info


@router.get("/{controller}/status")
async def get_controller_status(controller: str):
    controller = get_controller(controller)

    return controller.status()


@router.get("/{controller}/node/{node}")
async def get_node_info(controller: str,
                        node: str):
    controller = get_controller(controller)
    node = get_node(controller, node)

    return node.info


@router.get("/{controller}/status/{node}")
async def get_node_status(controller: str,
                          node: str):
    controller = get_controller(controller)
    node = get_node(controller, node)

    return node.status


@router.post("/{controller}/node/{node}")
async def post_node_instruction(request: Request,
                                controller: str,
                                node: str):
    controller = get_controller(controller)
    node = get_node(controller, node)

    try:
        data = await request.json()
    except JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid instruction or no body provided")

    instructions = data.get("instructions", [])

    if not instructions:
        raise HTTPException(status_code=400, detail="no instructions provided")

    if isinstance(instructions, str):
        instructions = [instructions]

    try:
        response = {}
        if "create" in instructions:
            status = str(node.create_instance())
            response['create'] = status
        if "build" in instructions:
            status = controller.build_node(node)
            response['build'] = status
        if "start" in instructions:
            status = controller.start_node(node)
            response['start'] = status
        if "stop" in instructions:
            status = controller.stop_node(node)
            response['stop'] = status
        # if response is empty, no valid instructions were provided
        if not response:
            raise HTTPException(status_code=400, detail="invalid instruction")

    except HTTPException as e:
        raise e

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return response

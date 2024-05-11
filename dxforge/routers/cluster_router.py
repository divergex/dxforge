from enum import Enum
from json import JSONDecodeError
from typing import Dict

from fastapi import APIRouter, Request, HTTPException

from ..forge import Forge
from ..clusters import Controller, Node

router = APIRouter()
forge = Forge()


class Instruction(Enum):
    CREATE = "create"
    BUILD = "build"
    START = "start"
    STOP = "stop"


def get_controller(controller: str) -> Controller:
    if not (controller := forge.orchestrator.controllers.get(controller, None)):
        raise HTTPException(status_code=404, detail="controller not found")
    return controller


def get_node(controller: Controller, node: str) -> Node:
    if not (node := controller.nodes.get(node, None)):
        raise HTTPException(status_code=404, detail="node not found")
    return node


def execute(controller: Controller, node: Node, instructions: Dict[Instruction, dict]) -> dict:
    response = {}

    for instruction, kwargs in instructions.items():
        instruction = Instruction(instruction)

        try:
            if instruction == Instruction.BUILD:
                response[instruction] = controller.build_node(node, **kwargs)
            elif instruction == Instruction.CREATE:
                response[instruction] = controller.create_instance(node, **kwargs)
            elif instruction == Instruction.START:
                response[instruction] = controller.start_node(node)
            elif instruction == Instruction.STOP:
                response[instruction] = controller.stop_node(node)
        except Exception as e:
            response[instruction] = {"error": str(e)}

    return response


@router.get("/")  # status
async def get_status():
    return forge.orchestrator.status()


@router.get("/info")
async def get_info():
    return forge.orchestrator.info


@router.get("/{controller}/")
async def get_controller_status(controller: str):
    controller = get_controller(controller)

    return controller.status()


@router.get("/{controller}/info")
async def get_controller_info(controller: str):
    controller = get_controller(controller)

    return controller.info


@router.get("/{controller}/node/{node}")
async def get_node_status(controller: str,
                          node: str):
    controller = get_controller(controller)
    node = get_node(controller, node)

    return node.status


@router.get("/{controller}/node/{node}/info")
async def get_node_info(controller: str,
                        node: str):
    controller = get_controller(controller)
    node = get_node(controller, node)

    return node.info


@router.post("/{controller}/node/{node}")  # Example: {"instructions": {"create": {"name": "test"}}}
async def post_node_instruction(request: Request,
                                controller: str,
                                node: str):
    controller = get_controller(controller)
    node = get_node(controller, node)

    try:
        data = await request.json()
    except JSONDecodeError:
        raise HTTPException(status_code=400, detail="invalid instruction or no body provided")

    instructions = data.get("instructions", {})

    if not instructions:
        raise HTTPException(status_code=400, detail="no instructions provided")

    response = execute(controller, node, instructions)

    return response

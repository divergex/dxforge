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


class NodeInstruction:
    def __init__(self, controller: Controller, node: Node):
        self.controller = controller
        self.node = node

        self.instructions = {
            "create": self.node.create_instance,
            "build": self.controller.build_node,
            "start": self.controller.start_node,
            "stop": self.controller.stop_node,
        }

    @staticmethod
    def get_kwargs(instructions, instruction):
        if isinstance(instructions[instruction], dict):
            return instructions[instruction]
        return {}

    def get_func(self, instruction):
        return self.instructions.get(instruction, None)

    def execute(self, instructions, instruction):
        func = self.get_func(instruction)
        kwargs = self.get_kwargs(instructions, instruction)
        return func(**kwargs)


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

    instructions: dict = data.get("instructions", {})

    if not instructions:
        raise HTTPException(status_code=400, detail="no instructions provided")

    node_instruction = NodeInstruction(controller, node)
    response = {}

    for instruction in instructions:
        try:
            if instruction not in node_instruction.instructions:
                raise HTTPException(status_code=400, detail=f"invalid instruction: {instruction}")
            response[instruction] = node_instruction.execute(instructions, instruction)
        except HTTPException as e:
            response[instruction] = {"error": e.detail}
        except Exception as e:
            response[instruction] = {"error": str(e)}

    return response

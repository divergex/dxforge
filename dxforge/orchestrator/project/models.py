import json
import textwrap
from typing import Optional, Tuple, Dict, List

from pydantic import BaseModel, Field


class BuildData(BaseModel):
    """
    Dockerfile config to rebuild dockerfile
    """
    base_image: str
    entrypoint_cmd: List[str]
    open_ports: Dict[str, int] = Field(default_factory=dict)
    build_args: Dict[str, str] = {}

    def dockerfile(self) -> str:
        ports = " ".join(str(p) for p in self.open_ports.values())
        expose = f"EXPOSE {ports}" if ports else ""
        entrypoint_json = json.dumps(self.entrypoint_cmd)  # <-- convert list to JSON
        dockerfile = f"""
        FROM {self.base_image}
        COPY . /app
        WORKDIR /app
        {expose}
        ENTRYPOINT {entrypoint_json}
        """
        return textwrap.dedent(dockerfile).strip()


class ProjectData(BaseModel):
    owner: str
    name: str
    description: Optional[str] = None
    tags: list[str] = []

    build_data: BuildData
    storage_path: Optional[str] = None

    @classmethod
    def model_name(cls):
        return "project"

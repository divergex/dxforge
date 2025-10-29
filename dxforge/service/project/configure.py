import io
import os
import pathlib
import tarfile
import tempfile

import docker
from docker.errors import DockerException
from fastapi import Path, APIRouter, Request, HTTPException, Body
from starlette.responses import HTMLResponse
from starlette.templating import Jinja2Templates

router = APIRouter()

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/{project_name}/configure", response_class=HTMLResponse)
async def configure_editor(request: Request, project_name: str = Path(..., description="Name of the project")):
    # format project name: if string return HTML_TEMPLATE.format(project_name=project_name), but is html
    return templates.TemplateResponse("editor.html", {"request": request, "project_name": project_name})


def create_dockerfile(content: str, project_name: str):
    client = docker.from_env()
    with tempfile.TemporaryDirectory() as tmpdir:
        dockerfile_content = content.encode().decode('unicode_escape')

        dockerfile_path = pathlib.Path(tmpdir) / "Dockerfile"
        dockerfile_path.write_text(dockerfile_content)

        try:
            client.images.build(path=tmpdir, rm=True, tag=f"{project_name}:test")
        except docker.errors.BuildError as e:
            raise HTTPException(status_code=400, detail=f"Docker build failed: {e}")
        except docker.errors.APIError as e:
            raise HTTPException(status_code=500, detail=f"Docker API error: {e}")

    return True


@router.post("/{project_name}/configure")
async def configure_project(
        project_name: str = Path(..., description="Name of the project"),
        payload: dict = Body(...),
):
    content = payload.get("content")
    # verify if content can be correctly parsed as Dockerfile, use docker api if necessary
    if not content:
        raise HTTPException(status_code=400, detail="No Dockerfile content provided")

    content = content.replace("\r\n", "\n")

    valid = create_dockerfile(content, project_name)
    if not valid:
        raise HTTPException(status_code=400, detail="Invalid Dockerfile content")
    else:
        return {"detail": "Dockerfile validated"}

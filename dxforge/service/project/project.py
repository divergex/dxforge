import uuid
from typing import Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from orchestrator.project import ProjectManager
from orchestrator.user import UserManager

router = APIRouter()

um = UserManager()

bearer_scheme = HTTPBearer()  # this adds the lock icon in Swagger

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    token = credentials.credentials  # just the token part
    user_id = um.verify_jwt(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return int(user_id)


@router.get("/")
async def list_projects(uid: int = Depends(get_current_user)):
    pm = ProjectManager()
    return pm.get_projects(uid)

@router.post("/")
async def create_project(name: str, tag: Optional[str] = None, file: UploadFile = File(...), uid: int = Depends(get_current_user)):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")

    # store zip to disk
    # temp uuid
    temp_uuid = str(uuid.uuid4())
    with open(f"/tmp/{temp_uuid}.zip", "wb") as buffer:
        buffer.write(file.file.read())

    pm = ProjectManager()
    project_id = pm.create_project(uid, name, tag)

    pm.upload_zip(project_id, f"/tmp/{temp_uuid}.zip")
    return {"project_id": project_id}

@router.delete("/{project_name}")
async def delete_project(project_name: str, uid: int = Depends(get_current_user)):
    pm = ProjectManager()

    try:
        pm.delete_project(uid, project_name)
        return {"detail": "Project deleted"}
    except ValueError:
        raise HTTPException(status_code=403, detail="No project with this name was found.")


from .configure import router as configure_router

@router.get("/{project_name}/")
async def get_project(project_name: str, uid: int = Depends(get_current_user)):
    # get info about project
    pm = ProjectManager()
    project = pm.get_project(project_name)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

router.include_router(configure_router)
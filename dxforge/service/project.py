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


@router.get("/list")
async def list_projects(uid: int = Depends(get_current_user)):
    pm = ProjectManager()
    return pm.get_projects(uid)

@router.post("/")
async def create_project(tag: Optional[str] = None, file: UploadFile = File(...), uid: int = Depends(get_current_user)):
    if not file.filename.endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip files are allowed")

    # store zip to disk
    # temp uuid
    temp_uuid = str(uuid.uuid4())
    with open(f"/tmp/{temp_uuid}.zip", "wb") as buffer:
        buffer.write(file.file.read())

    pm = ProjectManager()
    project_id = pm.create_project(uid, "myproj", tag)

    print({
        "project_id": project_id,
        "user_id": uid,
    })
    pm.upload_zip(project_id, f"/tmp/{temp_uuid}.zip")

@router.delete("/{project_id}")
async def delete_project(project_id: int, uid: int = Depends(get_current_user)):
    pm = ProjectManager()

    # make sure user has rights to project
    user_projects = pm.get_projects(uid)
    for project in user_projects:
        if project.id == project_id:
            pm.delete_project(project_id)
            # also remove from db

            return {"detail": "Project deleted"}

    raise HTTPException(status_code=403, detail="You don't have access to this project")

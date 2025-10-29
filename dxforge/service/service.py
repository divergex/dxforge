from fastapi import FastAPI

from .schedule import router as schedule_router
from .project import router as project_router
from .users import router as user_router

app = FastAPI()
app.include_router(schedule_router, prefix="/scheduler", tags=["Scheduler"])
app.include_router(project_router, prefix="/project", tags=["Project"])
app.include_router(user_router, prefix="/user", tags=["User"])
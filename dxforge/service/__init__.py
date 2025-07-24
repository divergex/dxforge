from fastapi import FastAPI

from .schedule import router as schedule_router

def main():
    app = FastAPI()
    app.include_router(schedule_router, prefix="/scheduler")
    return app

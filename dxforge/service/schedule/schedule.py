from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict
from starlette.responses import JSONResponse
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.background import BackgroundScheduler
import uuid
from dxforge.orchestrator import Orchestrator

router = APIRouter()

jobstores = {'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')}
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()
orchestrator = Orchestrator()
job_registry: Dict[str, str] = {}

strategy_store = {
    "wick": "examples/wick/config.yaml",
}

class Schedule(BaseModel):
    name: str = Field(
        ...,
        json_schema_extra={"example": "wick"},
        description="Strategy name"
    )
    cron: str = Field(
        ...,
        json_schema_extra={"example": "*/5 * * * *"},
        description="Cron expression (minute hour day month day_of_week)"
    )


class Action(BaseModel):
    name: str

@router.get("/strategies")
def list_strategies():
    return list(strategy_store.keys())

def run_strategy_job(strategy_name: str):
    print(f"[Scheduler] Running strategy: {strategy_name}")
    orchestrator.run(strategy_store[strategy_name])

@router.post("/schedule")
def schedule_strategy(schedule: Schedule):
    if schedule.name not in strategy_store:
        raise HTTPException(status_code=404, detail="Strategy not found")

    job_id = str(uuid.uuid4())

    try:
        trigger = CronTrigger.from_crontab(schedule.cron)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    scheduler.add_job(
        run_strategy_job,
        trigger,
        id=job_id,
        name=schedule.name,
        args=[schedule.name]
    )
    job_registry[job_id] = schedule.name
    return {"job_id": job_id}

@router.get("/schedules")
def list_schedules():
    jobs = scheduler.get_jobs()
    result = []
    for job in jobs:
        is_paused = scheduler.get_job(job.id).next_run_time is None
        result.append({
            "job_id": job.id,
            "strategy_name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
            "paused": is_paused,
        })
    return JSONResponse(content=result)

@router.delete("/schedule/{job_id}")
def delete_schedule(job_id: str):
    if job_id not in job_registry:
        raise HTTPException(status_code=404, detail="Job not found")
    scheduler.remove_job(job_id)
    del job_registry[job_id]
    return {"detail": "Job deleted"}

@router.delete("/strategy/{container_name}")
def delete(container_name: str):
    removed = orchestrator.remove(container_name)
    return {"detail": "Removed" if removed else "Removed"}

@router.post("/run")
def run_strategy(action: Action):
    if action.name not in strategy_store:
        raise HTTPException(status_code=404, detail="Strategy not found")
    container_name = orchestrator.run(strategy_store[action.name])
    return {"detail": f"Started {action.name} with container {container_name}"}

@router.post("/stop")
def stop_strategy(action: Action):
    if action.name not in strategy_store:
        raise HTTPException(status_code=404, detail="Strategy not found")
    scheduler.pause_job(action.name)
    orchestrator.stop(action.name)

@router.get("/logs")
def log_strategy(name: str = Query(..., description="Name of the strategy")):
    logs = orchestrator.logs(name)
    return logs

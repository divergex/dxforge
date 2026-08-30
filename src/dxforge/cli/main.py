import os
import subprocess
from importlib import metadata
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select
from sqlalchemy.orm import Session

app = typer.Typer()
run_app = typer.Typer(help="Run platform components in the foreground.")
worker_app = typer.Typer(help="Manage background scheduler workers.")

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SECRETS = _REPO_ROOT / "secrets"


def _read_secret(name: str) -> str | None:
    path = _SECRETS / name
    return path.read_text().strip() if path.exists() else None


def _seed_environment() -> None:
    """Fill FORGE_* from ./secrets when unset so commands work right after bootstrap."""
    if os.environ.get("FORGE_DATABASE_URL"):
        return
    db_user = _read_secret("postgres_app_user.txt") or "forge_app"
    db_password = _read_secret("postgres_app_password.txt")
    if db_password:
        _ = os.environ.setdefault(
            "FORGE_DATABASE_URL",
            f"postgresql+psycopg://{db_user}:{db_password}@127.0.0.1:5432/forge",
        )
    for var, file in (
        ("FORGE_BAO_INGEST_TOKEN", "openbao_app_server_token.txt"),
        ("FORGE_BAO_EXEC_TOKEN", "openbao_worker_token.txt"),
        ("FORGE_MINIO_INGEST_SECRET_KEY", "minio_app_server_secret.txt"),
        ("FORGE_MINIO_EXEC_SECRET_KEY", "minio_worker_secret.txt"),
        ("FORGE_API_KEY_PEPPER", "api_key_pepper.txt"),
        ("FORGE_REGISTRY_PASSWORD", "registry_password.txt"),
    ):
        value = _read_secret(file)
        if value:
            _ = os.environ.setdefault(var, value)


_seed_environment()


def _version() -> str:
    try:
        return metadata.version("dxforge")
    except metadata.PackageNotFoundError:
        return "dev"


@app.command()
def bootstrap() -> None:
    """Bring up infra (Postgres, MinIO, OpenBao, registry), secrets, and migrations."""
    script = _REPO_ROOT / "scripts" / "run-setup.sh"
    _ = subprocess.run([str(script)], cwd=_REPO_ROOT, check=True)


@app.command()
def migrate() -> None:
    """Apply database migrations (alembic upgrade head)."""
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(_REPO_ROOT / "alembic.ini"))
    command.upgrade(cfg, "head")


@app.command(hidden=True)
def worker_run(
    interval: Annotated[float, typer.Option(help="Poll interval in seconds")] = 30.0,
) -> None:
    """Foreground scheduler loop; spawned by `forge worker start`."""
    from dxforge.scheduler.dispatcher import run_forever

    run_forever(interval_seconds=interval)


@run_app.command("api")
def run_api(
    host: Annotated[str, typer.Option(help="Bind address")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port")] = 8000,
) -> None:
    """Start the HTTP API server."""
    import uvicorn

    from dxforge.api.main import create_app

    uvicorn.run(create_app(version=_version()), host=host, port=port)


@worker_app.command("start")
def worker_start(
    interval: Annotated[float, typer.Option(help="Poll interval in seconds")] = 30.0,
) -> None:
    """Start a background scheduler worker and register it."""
    from dxforge.cli.workers import start as start_worker

    info = start_worker(interval)
    print(f"worker {info.worker_id} started (pid {info.pid})")


@worker_app.command("list")
def worker_list() -> None:
    """List workers, schedules, and their owner tenants."""
    from dxforge.cli.workers import list_workers

    workers = list_workers()
    if workers:
        print("workers:")
        for w in workers:
            print(f"  {w.worker_id}  pid={w.pid}  {w.status}  started={w.started_at}")
    else:
        print("no workers running")
    _print_schedules()


@worker_app.command("stop")
def worker_stop(worker_id: str) -> None:
    """Stop a background worker by id."""
    from dxforge.cli.workers import stop as stop_worker

    info = stop_worker(worker_id)
    if info is None:
        raise typer.BadParameter(f"unknown worker {worker_id!r}")
    print(f"worker {info.worker_id} stopped (pid {info.pid})")


def _print_schedules() -> None:
    from dxforge.db.models import Function, Schedule, Tenant
    from dxforge.db.session import engine, session_factory

    rows: list[tuple[str, str, str, str, str, str, str]] = []
    with Session(bind=engine) as lookup:
        tenants = lookup.execute(select(Tenant.id, Tenant.name)).tuples().all()
    for tenant_id, tenant_name in tenants:
        session = session_factory(tenant_id)
        try:
            for schedule in session.execute(select(Schedule)).scalars().all():
                function = session.get(Function, schedule.function_id)
                rows.append(
                    (
                        tenant_name,
                        str(schedule.id)[:8],
                        function.name if function is not None else "?",
                        schedule.rule,
                        "on" if schedule.enabled else "off",
                        schedule.executor_backend,
                        schedule.last_fired_at.isoformat(timespec="minutes")
                        if schedule.last_fired_at is not None
                        else "-",
                    )
                )
        finally:
            session.close()
    if not rows:
        print("no schedules")
        return
    print("schedules:")
    for tenant, schedule_id, function, rule, enabled, backend, last_fired in rows:
        line = f"  {tenant:<12} {schedule_id}  {function:<12} {enabled:<3} "
        line += f"{backend:<8} last={last_fired}  rule={rule}"
        print(line)


app.add_typer(run_app, name="run")
app.add_typer(worker_app, name="worker")


if __name__ == "__main__":
    app()

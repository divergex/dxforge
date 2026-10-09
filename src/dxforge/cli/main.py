import os
import subprocess
from importlib import metadata, resources
from pathlib import Path
from typing import Annotated

import typer
from sqlalchemy import select
from sqlalchemy.orm import Session

from dxforge.stack import (
    StackError,
    compose_logs,
    init_stack,
    require_stack,
    run_compose,
    stack_dir,
)
from dxforge.stack.secrets import generate_root_secrets, read_secret

app = typer.Typer()
run_app = typer.Typer(help="Run platform components in the foreground.")
worker_app = typer.Typer(help="Manage background scheduler workers.")
db_app = typer.Typer(help="Database maintenance.")

DirOption = Annotated[
    Path | None,
    typer.Option(
        "--dir",
        help="Stack directory (default: $FORGE_STACK_DIR, else the current directory).",
    ),
]

INFRA_SERVICES = ("postgres", "minio", "openbao", "registry")


def _root(directory: Path | None) -> Path:
    return stack_dir(directory)


def _stack_root(directory: Path | None) -> Path:
    return require_stack(_root(directory))


def _seed_environment(root: Path) -> None:
    """Fill FORGE_* from <stack>/secrets when unset, so commands work right after bootstrap."""
    db_user = read_secret(root, "postgres_app_user.txt") or "forge_app"
    db_password = read_secret(root, "postgres_app_password.txt")
    if db_password:
        _ = os.environ.setdefault(
            "FORGE_DATABASE_URL",
            f"postgresql+psycopg://{db_user}:{db_password}@127.0.0.1:5432/forge",
        )
    for var, name in (
        ("FORGE_BAO_INGEST_TOKEN", "openbao_app_server_token.txt"),
        ("FORGE_BAO_EXEC_TOKEN", "openbao_worker_token.txt"),
        ("FORGE_MINIO_INGEST_SECRET_KEY", "minio_app_server_secret.txt"),
        ("FORGE_MINIO_EXEC_SECRET_KEY", "minio_worker_secret.txt"),
        ("FORGE_API_KEY_PEPPER", "api_key_pepper.txt"),
        ("FORGE_REGISTRY_PASSWORD", "registry_password.txt"),
    ):
        value = read_secret(root, name)
        if value:
            _ = os.environ.setdefault(var, value)


def _version() -> str:
    try:
        return metadata.version("dxforge")
    except metadata.PackageNotFoundError:
        return "dev"


def _step(message: str) -> None:
    import time

    print(f"\n==> [{time.strftime('%H:%M:%S')}] {message}")


@app.command()
def init(
    dest: Annotated[Path, typer.Argument(help="Directory to render the stack into.")] = Path(
        "."
    ),
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing stack files.")
    ] = False,
    image: Annotated[
        str | None,
        typer.Option("--image", help="Container image to reference (default: the installed version)."),
    ] = None,
) -> None:
    """Render the compose stack + bootstrap scripts and generate root secrets."""
    try:
        result = init_stack(dest, image=image, force=force)
    except StackError as error:
        raise typer.BadParameter(str(error))
    print(f"stack rendered in {result.root}")
    print(f"  image:   {result.image}")
    print(f"  files:   {len(result.files)}")
    if result.secrets:
        print(f"  secrets: {', '.join(result.secrets)}")
    else:
        print("  secrets: already present")
    print(f"\nnext: forge up --dir {result.root} && forge bootstrap --dir {result.root}")


@app.command()
def up(directory: DirOption = None) -> None:
    """Start Postgres, MinIO, OpenBao and the registry."""
    root = _stack_root(directory)
    _step("starting infrastructure (first image pull may take a while)")
    _ = run_compose(root, ["up", "-d", *INFRA_SERVICES])
    _ = run_compose(root, ["ps"])


@app.command()
def down(
    directory: DirOption = None,
    volumes: Annotated[
        bool, typer.Option("--volumes", help="Also delete data and credential volumes.")
    ] = False,
) -> None:
    """Stop the stack; --volumes erases Postgres, MinIO, OpenBao and registry data."""
    root = _stack_root(directory)
    args = ["down"]
    if volumes:
        args.append("-v")
    _ = run_compose(root, args)


@app.command()
def bootstrap(directory: DirOption = None) -> None:
    """Start infrastructure, bootstrap credentials, and apply migrations."""
    root = _stack_root(directory)
    created = generate_root_secrets(root)
    if created:
        print(f"generated root secrets: {', '.join(created)}")

    steps: list[tuple[str, list[str]]] = [
        ("checking docker", []),
        (
            "starting Postgres, MinIO, OpenBao and registry (first image pull may take a while)",
            ["up", "-d", *INFRA_SERVICES],
        ),
        (
            "bootstrapping OpenBao: init/unseal, transit engine, policies, scoped tokens",
            ["run", "--rm", "openbao-bootstrap"],
        ),
        (
            "bootstrapping MinIO: tenant-code bucket + ingest/execution service accounts",
            ["run", "--rm", "minio-bootstrap"],
        ),
        ("bootstrapping registry auth (htpasswd)", ["run", "--rm", "registry-bootstrap"]),
        ("preparing the application database role", ["run", "--rm", "db-prepare-role"]),
        ("running database migrations", ["run", "--rm", "db-migrate"]),
    ]

    current = steps[0][0]
    try:
        for label, args in steps:
            current = label
            _step(label)
            if not args:
                _ = subprocess.run(
                    ["docker", "info"], check=True, capture_output=True, text=True
                )
                continue
            _ = run_compose(root, args)
    except (subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"\n!!! dxforge setup failed at: {current} ({error})")
        print("!!! Recent logs:")
        print(compose_logs(root))
        raise typer.Exit(code=1)

    print("\ndxforge is up.")
    print(f"   credentials are in {root / 'secrets'}")
    _ = run_compose(root, ["ps"])


@app.command()
def migrate(directory: DirOption = None) -> None:
    """Apply database migrations (alembic upgrade head) without an alembic.ini."""
    import logging

    from alembic import command
    from alembic.config import Config

    root = _stack_root(directory)
    _seed_environment(root)

    # alembic's upgrade messages go to a logger with no handler without this
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5.5s [%(name)s] %(message)s")

    config = Config()
    config.set_main_option(
        "script_location", str(resources.files("dxforge.db.migrations"))
    )
    command.upgrade(config, "head")
    print("migrations applied (head)")


@db_app.command("prepare-role")
def db_prepare_role(directory: DirOption = None) -> None:
    """Create the RLS-scoped application role and apply its grants (superuser)."""
    root = _stack_root(directory)
    _seed_environment(root)

    from dxforge.config import settings
    from dxforge.db.roles import app_password, prepare_app_role

    url = os.environ.get("FORGE_MIGRATE_URL") or settings.database_url
    messages = prepare_app_role(
        url,
        app_password(root),
        app_user=os.environ.get("POSTGRES_APP_USER", "forge_app"),
        superuser=os.environ.get("POSTGRES_USER", "forge"),
    )
    for message in messages:
        print(message)


@app.command(hidden=True)
def worker_run(
    interval: Annotated[float, typer.Option(help="Poll interval in seconds")] = 30.0,
    directory: DirOption = None,
) -> None:
    """Foreground scheduler loop; spawned by `forge worker start`."""
    _seed_environment(_root(directory))

    from dxforge.scheduler.dispatcher import run_forever

    run_forever(interval_seconds=interval)


@run_app.command("api")
def run_api(
    host: Annotated[str, typer.Option(help="Bind address")] = "127.0.0.1",
    port: Annotated[int, typer.Option(help="Bind port")] = 8000,
    directory: DirOption = None,
) -> None:
    """Start the HTTP API server."""
    # Seed before importing anything that reads settings at import time
    # (dxforge.db.session builds the engine from settings.database_url).
    _seed_environment(_root(directory))

    import uvicorn

    from dxforge.api.main import create_app

    uvicorn.run(create_app(version=_version()), host=host, port=port)


@worker_app.command("start")
def worker_start(
    interval: Annotated[float, typer.Option(help="Poll interval in seconds")] = 30.0,
    directory: DirOption = None,
) -> None:
    """Start a background scheduler worker and register it."""
    from dxforge.cli.workers import start as start_worker

    info = start_worker(_root(directory), interval)
    print(f"worker {info.worker_id} started (pid {info.pid})")


@worker_app.command("list")
def worker_list(directory: DirOption = None) -> None:
    """List workers, schedules, and their owner tenants."""
    from dxforge.cli.workers import list_workers

    root = _root(directory)
    _seed_environment(root)
    workers = list_workers(root)
    if workers:
        print("workers:")
        for w in workers:
            print(f"  {w.worker_id}  pid={w.pid}  {w.status}  started={w.started_at}")
    else:
        print("no workers running")
    _print_schedules()


@worker_app.command("stop")
def worker_stop(
    worker_id: str,
    directory: DirOption = None,
) -> None:
    """Stop a background worker by id."""
    from dxforge.cli.workers import stop as stop_worker

    info = stop_worker(_root(directory), worker_id)
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
app.add_typer(db_app, name="db")


if __name__ == "__main__":
    app()

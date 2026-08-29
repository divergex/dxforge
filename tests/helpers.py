import uuid

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine


def insert_project(conn: Connection, tenant_id: uuid.UUID, name: str = "p") -> uuid.UUID:
    return uuid.UUID(str(conn.execute(
        text("INSERT INTO projects (id, tenant_id, name) VALUES (:id, :tid, :name) RETURNING id"),
        {"id": uuid.uuid4(), "tid": str(tenant_id), "name": name},
    ).scalar_one()))


def insert_version(
    conn: Connection,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    version_number: int = 1,
    runtime: str = "python-3.11",
) -> uuid.UUID:
    return uuid.UUID(str(conn.execute(
        text(
            "INSERT INTO versions (id, tenant_id, project_id, version_number, runtime, code_object_key, wrapped_dek, key_version) "
            "VALUES (:id, :tid, :pid, :vn, :runtime, 'k', :wrapped, 1) RETURNING id"
        ),
        {
            "id": uuid.uuid4(),
            "tid": str(tenant_id),
            "pid": str(project_id),
            "vn": version_number,
            "runtime": runtime,
            "wrapped": b"\x00" * 16,
        },
    ).scalar_one()))


def insert_function(
    conn: Connection,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    name: str = "f",
    handler: str = "main.py",
) -> uuid.UUID:
    return uuid.UUID(str(conn.execute(
        text(
            "INSERT INTO functions (id, tenant_id, project_id, version_id, name, handler) "
            "VALUES (:id, :tid, :pid, :vid, :name, :handler) RETURNING id"
        ),
        {
            "id": uuid.uuid4(),
            "tid": str(tenant_id),
            "pid": str(project_id),
            "vid": str(version_id),
            "name": name,
            "handler": handler,
        },
    ).scalar_one()))


def seed_project_version(
    engine: Engine, tenant_id: uuid.UUID, version_number: int = 1
) -> tuple[uuid.UUID, uuid.UUID]:
    """Project + version rows; RLS requires the tenant context in the transaction."""
    with engine.begin() as conn:
        _ = conn.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        project_id = insert_project(conn, tenant_id)
        version_id = insert_version(conn, tenant_id, project_id, version_number)
    return project_id, version_id

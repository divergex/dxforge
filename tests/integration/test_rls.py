import uuid

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from dxforge.config import settings

pytestmark = pytest.mark.integration

TENANT_TABLES = ("functions", "versions", "schedules", "executions")


@pytest.fixture(scope="module")
def engine() -> Engine:
    return create_engine(settings.database_url)


def _set_tenant(conn: Connection, tenant_id: uuid.UUID) -> None:
    # SET accepts no bind parameters (psycopg server-side binding)
    _ = conn.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))


def test_zero_rows_without_tenant_context(engine) -> None:
    with engine.connect() as conn:
        for table in TENANT_TABLES:
            count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one()
            assert count == 0


def test_tenant_isolation_between_contexts(engine) -> None:
    tenant_a, tenant_b = uuid.uuid4(), uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO tenants (id, name, api_key_hash) VALUES (:id, 'a', 'h')"),
            {"id": tenant_a},
        )
        conn.execute(
            text("INSERT INTO tenants (id, name, api_key_hash) VALUES (:id, 'b', 'h')"),
            {"id": tenant_b},
        )
    with engine.begin() as conn:
        _set_tenant(conn, tenant_a)
        func_id = conn.execute(
            text(
                "INSERT INTO functions (id, tenant_id, name) "
                "VALUES (:id, :tid, 'a') RETURNING id"
            ),
            {"id": uuid.uuid4(), "tid": str(tenant_a)},
        ).scalar_one()

    with engine.begin() as conn:
        _set_tenant(conn, tenant_a)
        assert conn.execute(text("SELECT count(*) FROM functions")).scalar_one() == 1

    with engine.begin() as conn:
        _set_tenant(conn, tenant_b)
        assert conn.execute(text("SELECT count(*) FROM functions")).scalar_one() == 0
        updated = conn.execute(
            text("UPDATE functions SET name = 'x' WHERE id = :id"), {"id": func_id}
        ).rowcount
        assert updated == 0

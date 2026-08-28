"""enable rls

Create Date: 2026-08-28

this file has been written with the help of a completion agent (git copilot),
and was based on an existing human-created sqlalchemy model.

"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TENANT_TABLES = ("functions", "versions", "schedules", "executions")
TENANT_CONTEXT = "current_setting('app.tenant_id', true)::uuid"


def upgrade() -> None:
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            + f"USING (tenant_id = {TENANT_CONTEXT}) "
            + f"WITH CHECK (tenant_id = {TENANT_CONTEXT})"
        )


def downgrade() -> None:
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

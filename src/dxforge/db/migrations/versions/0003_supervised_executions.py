"""supervised executions: health/timeouts, one-shot schedules, supervisor tracking

Create Date: 2026-11-17

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("functions", sa.Column("health_url", sa.String(1024), nullable=True))
    op.add_column(
        "functions",
        sa.Column("alive_timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
    )
    op.add_column(
        "functions",
        sa.Column("hard_timeout_seconds", sa.Integer(), nullable=True, server_default="300"),
    )
    # Existing rows keep the old fixed 300s; the default is dropped so an explicit
    # NULL (never time out) is storable instead of being replaced by it.
    op.alter_column("functions", "hard_timeout_seconds", server_default=None)

    op.alter_column("schedules", "rule", existing_type=sa.String(512), nullable=True)
    op.add_column(
        "schedules", sa.Column("trigger_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.alter_column("schedules", "executor_backend", server_default="host")

    op.alter_column("executions", "executor_backend", server_default="host")
    op.add_column("executions", sa.Column("supervisor_pid", sa.Integer(), nullable=True))
    op.add_column("executions", sa.Column("pid", sa.Integer(), nullable=True))
    op.add_column(
        "executions", sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "executions",
        sa.Column("stop_requested", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("executions", "stop_requested")
    op.drop_column("executions", "heartbeat_at")
    op.drop_column("executions", "pid")
    op.drop_column("executions", "supervisor_pid")
    op.alter_column("executions", "executor_backend", server_default="docker")

    op.alter_column("schedules", "executor_backend", server_default="docker")
    op.drop_column("schedules", "trigger_at")
    # Run-once schedules have no rule; give them a placeholder so NOT NULL holds.
    op.execute("""UPDATE schedules SET rule = '{"dates": []}' WHERE rule IS NULL""")
    op.alter_column("schedules", "rule", existing_type=sa.String(512), nullable=False)

    op.drop_column("functions", "hard_timeout_seconds")
    op.drop_column("functions", "alive_timeout_seconds")
    op.drop_column("functions", "health_url")

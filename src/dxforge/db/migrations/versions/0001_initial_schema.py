"""initial schema

Create Date: 2026-08-28

this file has been written with the help of a completion agent (git copilot),
and was based on an existing human-created sqlalchemy model.

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# TODO: hgave a programatic template/class for reusability of migrations like these instead of mako
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("api_key_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("build_tool", sa.String(16), nullable=False, server_default="none"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_projects_tenant_id", "projects", ["tenant_id"])

    op.create_table(
        "git_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("ciphertext", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_git_credentials_tenant_id", "git_credentials", ["tenant_id"])

    op.create_table(
        "versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("runtime", sa.String(64), nullable=False),
        sa.Column("build_tool", sa.String(16), nullable=False, server_default="none"),
        sa.Column("code_object_key", sa.String(512), nullable=False),
        sa.Column("wrapped_dek", sa.LargeBinary(), nullable=False),
        sa.Column("key_version", sa.Integer(), nullable=False),
        sa.Column("source_type", sa.String(16), nullable=True),
        sa.Column("git_repo_url", sa.String(1024), nullable=True),
        sa.Column(
            "git_credential_id",
            sa.Uuid(),
            sa.ForeignKey("git_credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "project_id", "version_number", name="uq_versions_project_number"
        ),
    )
    op.create_index("ix_versions_tenant_id", "versions", ["tenant_id"])
    op.create_index("ix_versions_project_id", "versions", ["project_id"])

    op.create_table(
        "functions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            sa.Uuid(),
            sa.ForeignKey("versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("handler", sa.String(512), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_functions_tenant_id", "functions", ["tenant_id"])
    op.create_index("ix_functions_project_id", "functions", ["project_id"])
    op.create_index("ix_functions_version_id", "functions", ["version_id"])

    op.create_table(
        "schedules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "function_id",
            sa.Uuid(),
            sa.ForeignKey("functions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            sa.Uuid(),
            sa.ForeignKey("versions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("rule", sa.String(512), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("last_fired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_schedules_tenant_id", "schedules", ["tenant_id"])
    op.create_index("ix_schedules_function_id", "schedules", ["function_id"])

    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "tenant_id",
            sa.Uuid(),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "schedule_id",
            sa.Uuid(),
            sa.ForeignKey("schedules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "function_id",
            sa.Uuid(),
            sa.ForeignKey("functions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "version_id",
            sa.Uuid(),
            sa.ForeignKey("versions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=False, server_default=""),
        sa.Column("stderr", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
    )
    op.create_index("ix_executions_tenant_id", "executions", ["tenant_id"])
    op.create_index("ix_executions_schedule_id", "executions", ["schedule_id"])
    op.create_index("ix_executions_function_id", "executions", ["function_id"])
    op.create_index("ix_executions_version_id", "executions", ["version_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("operator_id", sa.String(255), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_tenant_id", sa.Uuid(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("executions")
    op.drop_table("schedules")
    op.drop_table("functions")
    op.drop_table("versions")
    op.drop_table("git_credentials")
    op.drop_table("projects")
    op.drop_table("tenants")

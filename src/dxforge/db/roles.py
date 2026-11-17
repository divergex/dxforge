from __future__ import annotations

from pathlib import Path

import psycopg

from dxforge.stack.secrets import read_secret

APP_USER_DEFAULT = "forge_app"
SUPERUSER_DEFAULT = "forge"


class RoleError(RuntimeError):
    pass


def app_password(root: Path) -> str:
    password = read_secret(root, "postgres_app_password.txt")
    if not password:
        raise RoleError(f"no secrets/postgres_app_password.txt under {root}")
    return password


def prepare_app_role(
    database_url: str,
    password: str,
    *,
    app_user: str = APP_USER_DEFAULT,
    superuser: str = SUPERUSER_DEFAULT,
) -> list[str]:
    messages: list[str] = []
    dsn = database_url.replace("+psycopg", "")
    # needs a superuser DSN: this creates roles and default privileges
    with psycopg.connect(dsn, autocommit=True) as conn, conn.cursor() as cur:
        _ = cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
        if cur.fetchone() is None:
            # identifiers cannot be parameterised; app_user comes from compose config
            literal = password.replace("'", "''")
            cur.execute(f"CREATE ROLE {app_user} LOGIN PASSWORD '{literal}'")
            messages.append(f"created role {app_user}")
        else:
            messages.append(f"role {app_user} already exists")

        # Recreated schemas lose the default PUBLIC usage grant.
        cur.execute(f"GRANT USAGE ON SCHEMA public TO {app_user}")
        cur.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public "
            f"TO {app_user}"
        )
        cur.execute(
            f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {app_user}"
        )
        cur.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {superuser} IN SCHEMA public "
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {app_user}"
        )
        cur.execute(
            f"ALTER DEFAULT PRIVILEGES FOR ROLE {superuser} IN SCHEMA public "
            f"GRANT USAGE, SELECT ON SEQUENCES TO {app_user}"
        )
        messages.append("grants applied")
    return messages

import os

import psycopg

DATABASE_URL = (
    os.environ.get("FORGE_MIGRATE_URL") or os.environ.get("FORGE_DATABASE_URL") or ""
).replace("+psycopg", "")
if not DATABASE_URL:
    raise SystemExit("set FORGE_MIGRATE_URL or FORGE_DATABASE_URL")
SUPERUSER = os.environ.get("POSTGRES_USER", "forge")
APP_USER = os.environ.get("POSTGRES_APP_USER", "forge_app")
APP_PASSWORD = open("/run/secrets/postgres_app_password").read().strip()


def main() -> None:
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (APP_USER,))
            if cur.fetchone() is None:
                password_literal = APP_PASSWORD.replace("'", "''")
                cur.execute(
                    f"CREATE ROLE {APP_USER} LOGIN PASSWORD '{password_literal}'"
                )
                print(f"created role {APP_USER}")
            else:
                print(f"role {APP_USER} already exists")

            cur.execute(
                f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_USER}"
            )
            cur.execute(
                f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_USER}"
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {SUPERUSER} IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_USER}"
            )
            cur.execute(
                f"ALTER DEFAULT PRIVILEGES FOR ROLE {SUPERUSER} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_USER}"
            )
            print("grants applied")


if __name__ == "__main__":
    main()

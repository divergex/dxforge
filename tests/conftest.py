import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SECRETS_DIR = Path(os.environ.get("FORGE_STACK_DIR", ROOT / ".stack")) / "secrets"


def _read(name: str) -> str | None:
    path = SECRETS_DIR / name
    return path.read_text().strip() if path.exists() else None


def _seed_environment() -> None:
    if os.environ.get("FORGE_BAO_INGEST_TOKEN"):
        return
    db_user = _read("postgres_app_user.txt") or "forge_app"
    db_password = _read("postgres_app_password.txt")
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
        value = _read(file)
        if value:
            _ = os.environ.setdefault(var, value)


_seed_environment()

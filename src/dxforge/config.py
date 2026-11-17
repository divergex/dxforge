from functools import lru_cache
from pathlib import Path
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="FORGE_", env_file=".env", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://forge_app:forge_app@127.0.0.1:5432/forge"

    minio_endpoint: str = "127.0.0.1:9000"
    minio_bucket: str = "tenant-code"
    minio_secure: bool = False
    minio_ingest_access_key: str = "app-server-key"
    minio_ingest_secret_key: str = ""
    minio_exec_access_key: str = "worker-key"
    minio_exec_secret_key: str = ""

    bao_addr: str = "http://127.0.0.1:8200"
    bao_ingest_token: str = ""
    bao_exec_token: str = ""
    transit_key: str = "tenant-code"
    credentials_transit_key: str = "git-credentials"

    upload_dir: str = "./var/uploads"
    max_upload_bytes: int = 100 * 1024 * 1024
    max_archive_files: int = 5000
    default_runtime: str = "python-3.11"

    log_max_bytes: int = 1_000_000
    keep_versions: int = 5

    # Default hard timeout offered to new functions; a function may set None (never).
    execution_timeout_seconds: int = 300

    # Host-process supervision. Runtime state of live executions (logs, code) is
    # kept under execution_dir, which must be readable by both API and supervisors.
    execution_dir: str = str(Path(__file__).resolve().parents[2] / "var" / "executions")
    supervisor_heartbeat_seconds: float = 5.0
    supervisor_stale_seconds: float = 60.0
    health_check_interval_seconds: float = 5.0
    stop_grace_seconds: float = 10.0

    # Global salt mixed into tenant API-key hashes (see auth/api_keys.py).
    api_key_pepper: str = ""

    impersonation_ttl_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

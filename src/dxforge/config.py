from functools import lru_cache
from typing import ClassVar

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="FORGE_", env_file=".env", extra="ignore"
    )

    # Application role is RLS-scoped, non-superuser

    # These can/should be overwritten in .env file or environment variables
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

    upload_dir: str = "./var/uploads"
    max_upload_bytes: int = 100 * 1024 * 1024
    max_archive_files: int = 5000

    log_max_bytes: int = 1_000_000
    keep_versions: int = 5

    impersonation_ttl_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

import uuid
from typing import Self

import boto3
from botocore.config import Config as BotoConfig

from dxforge.config import settings


def build_key(
    tenant_id: uuid.UUID | str, project_id: uuid.UUID | str, version: int
) -> str:
    tenant = uuid.UUID(str(tenant_id))
    project = uuid.UUID(str(project_id))
    return f"{tenant}/{project}/{version}/code.tar.gz.enc"


class ObjectStore:
    """S3-compatible client"""

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = False,
    ) -> None:
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=f"{'https' if secure else 'http'}://{endpoint}",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            config=BotoConfig(
                signature_version="s3v4", s3={"addressing_style": "path"}
            ),
        )

    @classmethod
    def from_settings(cls, access_key: str, secret_key: str) -> Self:
        return cls(
            settings.minio_endpoint,
            access_key,
            secret_key,
            settings.minio_bucket,
            settings.minio_secure,
        )

    def put_object(self, key: str, data: bytes) -> None:
        self._client.put_object(Bucket=self._bucket, Key=key, Body=data)

    def get_object(self, key: str) -> bytes:
        response = self._client.get_object(Bucket=self._bucket, Key=key)
        return response["Body"].read()

    def delete_object(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)


def build_ingest_store() -> ObjectStore:
    return ObjectStore.from_settings(
        settings.minio_ingest_access_key, settings.minio_ingest_secret_key
    )


def build_execution_store() -> ObjectStore:
    return ObjectStore.from_settings(
        settings.minio_exec_access_key, settings.minio_exec_secret_key
    )

import uuid

import pytest
from botocore.exceptions import ClientError

from dxforge.config import settings
from dxforge.storage.object_store import ObjectStore, build_key

pytestmark = pytest.mark.skipif(
    not (settings.minio_ingest_secret_key and settings.minio_exec_secret_key),
    reason="MinIO credentials not configured (run make setup)",
)


def _ingest() -> ObjectStore:
    return ObjectStore(
        settings.minio_endpoint,
        settings.minio_ingest_access_key,
        settings.minio_ingest_secret_key,
        settings.minio_bucket,
        settings.minio_secure,
    )


def _execution() -> ObjectStore:
    return ObjectStore(
        settings.minio_endpoint,
        settings.minio_exec_access_key,
        settings.minio_exec_secret_key,
        settings.minio_bucket,
        settings.minio_secure,
    )


def test_build_key_format() -> None:
    tenant = uuid.uuid4()
    function = uuid.uuid4()
    assert build_key(tenant, function, 3) == f"{tenant}/{function}/3/code.tar.gz.enc"


def test_build_key_normalizes_uuid_strings() -> None:
    tenant = str(uuid.uuid4())
    function = str(uuid.uuid4())
    assert build_key(tenant, function, 1) == f"{tenant}/{function}/1/code.tar.gz.enc"


def test_build_key_rejects_non_uuid() -> None:
    with pytest.raises(ValueError):
        build_key("../../etc", uuid.uuid4(), 1)


def test_ingest_put_get_delete_roundtrip() -> None:
    key = build_key(uuid.uuid4(), uuid.uuid4(), 1)
    store = _ingest()
    store.put_object(key, b"ciphertext-bytes")
    try:
        assert store.get_object(key) == b"ciphertext-bytes"
    finally:
        store.delete_object(key)
    with pytest.raises(ClientError):
        store.get_object(key)


def test_execution_store_read_only() -> None:
    key = build_key(uuid.uuid4(), uuid.uuid4(), 1)
    _ = _ingest().put_object(key, b"ciphertext-bytes")
    try:
        assert _execution().get_object(key) == b"ciphertext-bytes"
        with pytest.raises(ClientError):
            _ = _execution().delete_object(key)
    finally:
        _ = _ingest().delete_object(key)

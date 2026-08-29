import pytest
from hvac.exceptions import Forbidden

from dxforge.config import settings
from dxforge.crypto.kms_client import TransitClient

pytestmark = pytest.mark.skipif(
    not (settings.bao_ingest_token and settings.bao_exec_token),
    reason="OpenBao tokens not configured (run make setup)",
)


def _client(token: str) -> TransitClient:
    return TransitClient(settings.bao_addr, token, settings.transit_key)


def test_generate_and_unwrap_roundtrip() -> None:
    dek, wrapped = _client(settings.bao_ingest_token).generate_data_key()
    assert len(dek) == 32
    unwrapped = _client(settings.bao_exec_token).unwrap_data_key(wrapped)
    assert unwrapped.as_bytes() == dek.as_bytes()
    dek.wipe()
    unwrapped.wipe()


def test_ingest_token_cannot_decrypt() -> None:
    ingest = _client(settings.bao_ingest_token)
    _dek, wrapped = ingest.generate_data_key()
    with pytest.raises(Forbidden):
        _ = ingest.unwrap_data_key(wrapped)


def test_execution_token_cannot_generate() -> None:
    execution = _client(settings.bao_exec_token)
    with pytest.raises(Forbidden):
        _ = execution.generate_data_key()

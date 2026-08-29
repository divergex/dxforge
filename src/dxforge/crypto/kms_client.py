import base64
from typing import Self, cast, final

import hvac

from dxforge.config import settings
from dxforge.crypto.wipe import SecretBytes

_Payload = dict[str, dict[str, str]]


@final
class TransitClient:
    """Thin OpenBao `transit` wrapper bound to one scoped token."""

    def __init__(self, url: str, token: str, transit_key: str) -> None:
        self._client = hvac.Client(url=url, token=token)
        self._key = transit_key

    def generate_data_key(self) -> tuple[SecretBytes, bytes]:
        response = cast(
            _Payload,
            self._client.secrets.transit.generate_data_key(
                name=self._key, key_type="plaintext"
            ),
        )
        return SecretBytes(_decode(response, "plaintext")), response["data"][
            "ciphertext"
        ].encode()

    def unwrap_data_key(self, wrapped_dek: bytes) -> SecretBytes:
        response = cast(
            _Payload,
            self._client.secrets.transit.decrypt_data(
                name=self._key, ciphertext=wrapped_dek.decode()
            ),
        )
        return SecretBytes(_decode(response, "plaintext"))

    @classmethod
    def from_settings(cls, token: str) -> Self:
        return cls(settings.bao_addr, token, settings.transit_key)


def _decode(payload: _Payload, key: str) -> bytes:
    return base64.b64decode(payload["data"][key])


def build_ingest_client() -> TransitClient:
    return TransitClient.from_settings(settings.bao_ingest_token)


def build_execution_client() -> TransitClient:
    return TransitClient.from_settings(settings.bao_exec_token)


def build_credential_client() -> TransitClient:
    return TransitClient(
        settings.bao_addr, settings.bao_ingest_token, settings.credentials_transit_key
    )


def key_version_from_wrapped(wrapped_dek: bytes) -> int:
    return int(wrapped_dek.decode().split(":")[1].removeprefix("v"))

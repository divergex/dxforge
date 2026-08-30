import tempfile
from pathlib import Path

from dxforge.crypto.envelope import decrypt_bytes
from dxforge.crypto.kms_client import build_execution_client
from dxforge.db.models import Version
from dxforge.storage.object_store import build_execution_store


def fetch_decrypt_to_file(version: Version) -> Path:
    """Plaintext artifact on an ephemeral path; caller deletes it in a finally."""
    ciphertext = build_execution_store().get_object(version.code_object_key)
    with build_execution_client().unwrap_data_key(version.wrapped_dek) as dek:
        plaintext = decrypt_bytes(dek, ciphertext)
    workdir = Path(tempfile.mkdtemp(prefix="dxforge-run-"))
    artifact = workdir / "artifact"
    _ = artifact.write_bytes(plaintext)
    return artifact

import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import override

from dxforge.build.sources.base import SourceAdapter
from dxforge.crypto.envelope import decrypt_bytes
from dxforge.crypto.kms_client import build_credential_client
from dxforge.db.models import GitCredential
from dxforge.db.session import session_factory


class GitSource(SourceAdapter):
    source_type = "git"

    def __init__(
        self, repo_url: str, tenant_id: uuid.UUID, credential_id: uuid.UUID | None
    ) -> None:
        self.repo_url: str = repo_url
        self.credential_id: uuid.UUID | None = credential_id
        self._tenant_id: uuid.UUID = tenant_id

    @override
    def fetch(self) -> Path:
        dest = Path(tempfile.mkdtemp(prefix="dxforge-src-"))
        key_path: Path | None = None
        env = os.environ.copy()
        try:
            if self.credential_id is not None:
                key_path = self._write_ssh_key()
                env["GIT_SSH_COMMAND"] = (
                    f"ssh -i {key_path} -o StrictHostKeyChecking=no "
                    "-o UserKnownHostsFile=/dev/null"
                )
            _ = subprocess.run(
                ["git", "clone", "--depth", "1", self.repo_url, str(dest)],
                env=env,
                check=True,
                capture_output=True,
            )
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
            raise
        finally:
            if key_path is not None:
                key_path.unlink(missing_ok=True)
        return dest

    def _write_ssh_key(self) -> Path:
        session = session_factory(self._tenant_id)
        try:
            credential = session.get(GitCredential, self.credential_id)
        finally:
            session.close()
        if credential is None:
            raise ValueError("credential not found")
        with build_credential_client().unwrap_data_key(credential.wrapped_dek) as dek:
            plaintext = decrypt_bytes(dek, credential.ciphertext)
        key_path = Path(tempfile.mkdtemp(prefix="dxforge-key-")) / "id_rsa"
        key_path.write_bytes(plaintext)
        key_path.chmod(0o600)
        return key_path

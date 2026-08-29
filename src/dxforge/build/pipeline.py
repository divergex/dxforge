import shutil
import uuid
from pathlib import Path

from sqlalchemy import select

from dxforge.build.sources.base import SourceAdapter
from dxforge.build.tools import TOOLS
from dxforge.config import settings
from dxforge.crypto.envelope import encrypt_bytes
from dxforge.crypto.kms_client import build_ingest_client, key_version_from_wrapped
from dxforge.db.models import Project, Version
from dxforge.db.session import session_factory
from dxforge.storage.object_store import build_ingest_store, build_key


class BuildError(ValueError):
    pass


def run_build(
    *,
    tenant_id: uuid.UUID,
    project_id: uuid.UUID,
    source: SourceAdapter,
    runtime: str | None = None,
    build_tool: str | None = None,
    build_command: str | None = None,
) -> Version:
    source_dir: Path | None = None
    artifact: Path | None = None
    dek = None
    try:
        source_dir = source.fetch()
        tool_name = build_tool or "none"
        try:
            tool = TOOLS[tool_name]
        except KeyError:
            raise BuildError(f"unknown build tool: {tool_name}")
        artifact = tool.build(source_dir, build_command)
        payload = artifact.read_bytes()

        dek, wrapped = build_ingest_client().generate_data_key()
        ciphertext = encrypt_bytes(dek, payload)

        session = session_factory(tenant_id)
        try:
            project = session.get(Project, project_id)
            if project is None:
                raise BuildError("project not found")
            previous = session.execute(
                select(Version)
                .where(Version.project_id == project_id)
                .order_by(Version.version_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            version_number = (previous.version_number + 1) if previous else 1
            resolved_runtime = runtime or (
                previous.runtime if previous else settings.default_runtime
            )
            key = build_key(tenant_id, project_id, version_number)
            build_ingest_store().put_object(key, ciphertext)
            version = Version(
                tenant_id=tenant_id,
                project_id=project_id,
                version_number=version_number,
                runtime=resolved_runtime,
                build_tool=tool.name,
                code_object_key=key,
                wrapped_dek=wrapped,
                key_version=key_version_from_wrapped(wrapped),
                source_type=source.source_type,
                git_repo_url=getattr(source, "repo_url", None),
                git_credential_id=getattr(source, "credential_id", None),
            )
            session.add(version)
            session.commit()
            session.refresh(version)
            return version
        finally:
            session.close()
    finally:
        if dek is not None:
            dek.wipe()
        if source_dir is not None:
            shutil.rmtree(source_dir, ignore_errors=True)
        if artifact is not None:
            artifact.unlink(missing_ok=True)

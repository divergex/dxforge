import shutil
import tempfile
import uuid
from pathlib import Path

from dxforge.build.packager import ArchiveError, extract_zip
from dxforge.build.sources.base import SourceAdapter
from dxforge.config import settings


class ZipSource(SourceAdapter):
    source_type = "zip"

    def __init__(self, file_id: str) -> None:
        self._file_id = uuid.UUID(file_id)

    def fetch(self) -> Path:
        staged = Path(settings.upload_dir) / f"{self._file_id}.zip"
        if not staged.exists():
            raise ArchiveError("staged upload not found")
        dest = Path(tempfile.mkdtemp(prefix="dxforge-src-"))
        try:
            extract_zip(staged, dest)
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
            raise
        return dest

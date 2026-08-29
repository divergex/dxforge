import zipfile
from pathlib import Path

from dxforge.config import settings


class ArchiveError(ValueError):
    pass


def validate_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > settings.max_archive_files:
            raise ArchiveError("archive contains too many files")
        if sum(info.file_size for info in entries) > settings.max_upload_bytes:
            raise ArchiveError("archive too large")
        for info in entries:
            parts = Path(info.filename).parts
            if not parts or parts[0] in ("..", "/") or any(p == ".." for p in parts):
                raise ArchiveError(f"unsafe path in archive: {info.filename!r}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ArchiveError(f"symlinks not allowed: {info.filename!r}")


def extract_zip(path: Path, dest: Path) -> None:
    validate_zip(path)
    with zipfile.ZipFile(path) as archive:
        archive.extractall(dest)

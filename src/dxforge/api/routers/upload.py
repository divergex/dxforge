import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from dxforge.api.schemas import UploadOut
from dxforge.config import settings

router = APIRouter(prefix="/upload", tags=["upload"])


@router.post("", status_code=201, response_model=UploadOut)
def upload_archive(file: UploadFile = File(...)) -> UploadOut:
    data = file.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="upload too large")
    if not data.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=400, detail="not a zip archive")
    staging = Path(settings.upload_dir)
    staging.mkdir(parents=True, exist_ok=True)
    file_id = uuid.uuid4()
    (staging / f"{file_id}.zip").write_bytes(data)
    return UploadOut(file_id=str(file_id))

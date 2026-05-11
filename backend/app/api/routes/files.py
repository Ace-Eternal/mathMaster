from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.models import AppUser
from app.services.auth import require_permission
from app.services.storage.factory import get_storage_service

router = APIRouter()
ALLOWED_FILE_PREFIXES = ("raw/", "mineu/", "slices/", "review/", "analysis/", "templates/")
ALLOWED_FILE_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp"}


def _validate_preview_key(file_key: str) -> str:
    normalized_key = file_key.replace("\\", "/").lstrip("/")
    if not normalized_key.startswith(ALLOWED_FILE_PREFIXES):
        raise HTTPException(status_code=404, detail="File not found")
    extension = "." + normalized_key.rsplit(".", 1)[-1].lower() if "." in normalized_key.rsplit("/", 1)[-1] else ""
    if extension not in ALLOWED_FILE_EXTENSIONS:
        raise HTTPException(status_code=404, detail="File not found")
    return normalized_key


@router.get("/{file_key:path}")
def get_storage_file(file_key: str, _user: AppUser = Depends(require_permission("question.read"))):
    """返回本地存储中的原始文件，供前端预览切片图片。"""
    preview_key = _validate_preview_key(file_key)
    storage = get_storage_service()
    try:
        if not storage.exists(preview_key):
            raise HTTPException(status_code=404, detail="File not found")
        resolved_path = storage.resolve_path_or_key(preview_key)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid file key") from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail="Current storage backend does not support direct file preview") from exc
    return FileResponse(resolved_path)

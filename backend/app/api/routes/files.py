from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.storage.factory import get_storage_service

router = APIRouter()


@router.get("/{file_key:path}")
def get_storage_file(file_key: str):
    """返回本地存储中的原始文件，供前端预览切片图片。"""
    storage = get_storage_service()
    if not storage.exists(file_key):
        raise HTTPException(status_code=404, detail="File not found")
    try:
        resolved_path = storage.resolve_path_or_key(file_key)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail="Current storage backend does not support direct file preview") from exc
    return FileResponse(resolved_path)

from app.core.config import settings
from app.services.storage.base import FileStorageService
from app.services.storage.local import LocalFileStorageService
from app.services.storage.sftp import SFTPFileStorageService


def get_storage_service() -> FileStorageService:
    backend = settings.storage_backend.lower()
    if backend == "sftp":
        return SFTPFileStorageService()
    return LocalFileStorageService()

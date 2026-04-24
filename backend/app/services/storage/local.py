from pathlib import Path
import shutil

from app.core.config import settings
from app.services.storage.base import FileStorageService


class LocalFileStorageService(FileStorageService):
    def __init__(self, base_dir: str | None = None) -> None:
        self.base_dir = Path(base_dir or settings.storage_base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _resolve(self, target_key: str) -> Path:
        safe_key = target_key.replace("\\", "/").lstrip("/")
        return self.base_dir / safe_key

    def save_file(self, file_bytes: bytes, target_key: str) -> str:
        path = self._resolve(target_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_bytes)
        return target_key

    def read_file(self, target_key: str) -> bytes:
        return self._resolve(target_key).read_bytes()

    def exists(self, target_key: str) -> bool:
        return self._resolve(target_key).exists()

    def move_file(self, old_key: str, new_key: str) -> str:
        source = self._resolve(old_key)
        target = self._resolve(new_key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
        return new_key

    def delete_file(self, target_key: str) -> bool:
        path = self._resolve(target_key)
        if path.exists():
            path.unlink()
            return True
        return False

    def delete_prefix(self, target_prefix: str) -> int:
        path = self._resolve(target_prefix)
        if not path.exists():
            return 0
        if path.is_file():
            path.unlink()
            return 1
        deleted_count = sum(1 for item in path.rglob("*") if item.is_file())
        shutil.rmtree(path)
        return deleted_count

    def mkdir_if_needed(self, target_prefix: str) -> None:
        self._resolve(target_prefix).mkdir(parents=True, exist_ok=True)

    def resolve_path_or_key(self, target_key: str) -> str:
        return str(self._resolve(target_key))

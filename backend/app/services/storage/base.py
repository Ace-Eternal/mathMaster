from __future__ import annotations

from abc import ABC, abstractmethod


class FileStorageService(ABC):
    @abstractmethod
    def save_file(self, file_bytes: bytes, target_key: str) -> str: ...

    @abstractmethod
    def read_file(self, target_key: str) -> bytes: ...

    @abstractmethod
    def exists(self, target_key: str) -> bool: ...

    @abstractmethod
    def move_file(self, old_key: str, new_key: str) -> str: ...

    @abstractmethod
    def delete_file(self, target_key: str) -> bool: ...

    @abstractmethod
    def mkdir_if_needed(self, target_prefix: str) -> None: ...

    @abstractmethod
    def resolve_path_or_key(self, target_key: str) -> str: ...

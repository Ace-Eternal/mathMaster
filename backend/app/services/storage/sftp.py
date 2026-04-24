from __future__ import annotations

import io
import posixpath
import stat
from contextlib import contextmanager
from pathlib import PurePosixPath

import paramiko
from tenacity import retry, stop_after_attempt, wait_fixed

from app.core.config import settings
from app.services.storage.base import FileStorageService


class SFTPFileStorageService(FileStorageService):
    def __init__(self) -> None:
        self.host = settings.sftp_host or ""
        self.port = settings.sftp_port
        self.username = settings.sftp_username or ""
        self.password = settings.sftp_password
        self.private_key = settings.sftp_private_key
        self.base_dir = settings.storage_base_dir.rstrip("/")
        self.timeout = settings.sftp_timeout_seconds

    @contextmanager
    def _client(self):
        transport = paramiko.Transport((self.host, self.port))
        transport.banner_timeout = self.timeout
        if self.private_key:
            pkey = paramiko.RSAKey.from_private_key(io.StringIO(self.private_key))
            transport.connect(username=self.username, pkey=pkey)
        else:
            transport.connect(username=self.username, password=self.password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            yield sftp
        finally:
            sftp.close()
            transport.close()

    def _full_path(self, target_key: str) -> str:
        safe_key = target_key.replace("\\", "/").lstrip("/")
        return posixpath.join(self.base_dir, safe_key)

    def _mkdir_recursive(self, sftp: paramiko.SFTPClient, remote_dir: str) -> None:
        current = PurePosixPath("/")
        for part in PurePosixPath(remote_dir).parts[1:]:
            current = current / part
            try:
                sftp.stat(str(current))
            except FileNotFoundError:
                sftp.mkdir(str(current))

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def save_file(self, file_bytes: bytes, target_key: str) -> str:
        remote_path = self._full_path(target_key)
        with self._client() as sftp:
            self._mkdir_recursive(sftp, posixpath.dirname(remote_path))
            with sftp.file(remote_path, "wb") as remote_file:
                remote_file.write(file_bytes)
        return target_key

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def read_file(self, target_key: str) -> bytes:
        with self._client() as sftp:
            with sftp.file(self._full_path(target_key), "rb") as remote_file:
                return remote_file.read()

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def exists(self, target_key: str) -> bool:
        with self._client() as sftp:
            try:
                sftp.stat(self._full_path(target_key))
                return True
            except FileNotFoundError:
                return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def move_file(self, old_key: str, new_key: str) -> str:
        old_path = self._full_path(old_key)
        new_path = self._full_path(new_key)
        with self._client() as sftp:
            self._mkdir_recursive(sftp, posixpath.dirname(new_path))
            sftp.rename(old_path, new_path)
        return new_key

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def delete_file(self, target_key: str) -> bool:
        with self._client() as sftp:
            try:
                sftp.remove(self._full_path(target_key))
                return True
            except FileNotFoundError:
                return False

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def delete_prefix(self, target_prefix: str) -> int:
        with self._client() as sftp:
            return self._delete_remote_tree(sftp, self._full_path(target_prefix))

    def _delete_remote_tree(self, sftp: paramiko.SFTPClient, remote_path: str) -> int:
        try:
            attributes = sftp.stat(remote_path)
        except FileNotFoundError:
            return 0
        if not stat.S_ISDIR(attributes.st_mode):
            sftp.remove(remote_path)
            return 1

        deleted_count = 0
        for item in sftp.listdir_attr(remote_path):
            child_path = posixpath.join(remote_path, item.filename)
            if stat.S_ISDIR(item.st_mode):
                deleted_count += self._delete_remote_tree(sftp, child_path)
            else:
                sftp.remove(child_path)
                deleted_count += 1
        sftp.rmdir(remote_path)
        return deleted_count

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
    def mkdir_if_needed(self, target_prefix: str) -> None:
        with self._client() as sftp:
            self._mkdir_recursive(sftp, self._full_path(target_prefix))

    def resolve_path_or_key(self, target_key: str) -> str:
        return self._full_path(target_key)

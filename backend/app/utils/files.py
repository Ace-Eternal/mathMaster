from __future__ import annotations

import hashlib
import json
import re
from pathlib import PurePosixPath
from uuid import uuid4

from slugify import slugify


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_dumps(data: object) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")


def build_storage_key(*parts: str, filename: str | None = None) -> str:
    normalized = [part.strip("/\\") for part in parts if part]
    if filename:
        normalized.append(filename)
    return str(PurePosixPath(*normalized))


def safe_storage_filename(original_name: str, *, prefix: str | None = None) -> str:
    original_name = (original_name or "file.bin").strip().replace("\\", "/").split("/")[-1]
    if "." in original_name:
        stem, ext = original_name.rsplit(".", 1)
        extension = f".{re.sub(r'[^A-Za-z0-9]+', '', ext)[:16].lower() or 'bin'}"
    else:
        stem = original_name
        extension = ".bin"
    slug = slugify(stem, separator="_", lowercase=False, allow_unicode=False)
    slug = re.sub(r"_+", "_", slug).strip("_") or "file"
    token = prefix or uuid4().hex[:8]
    return f"{token}_{slug}{extension}"


def random_prefixed_name(original_name: str) -> str:
    return safe_storage_filename(original_name)

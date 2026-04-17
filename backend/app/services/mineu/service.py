from __future__ import annotations

import io
import json
import time
import uuid
import zipfile
from typing import Any

import httpx

from app.core.config import settings
from app.utils.files import json_dumps


class MineuService:
    def __init__(self) -> None:
        self.base_url = (settings.mineu_base_url or "").rstrip("/")
        self.api_key = settings.mineu_api_key
        self.use_mock = settings.mineu_use_mock or not (self.base_url and self.api_key)
        self.poll_seconds = settings.mineu_poll_seconds
        self.max_attempts = settings.mineu_poll_max_attempts

    def convert_pdf(self, *, filename: str, file_bytes: bytes, job_type: str) -> dict[str, bytes]:
        if self.use_mock:
            return self._mock_convert(filename=filename, job_type=job_type)
        if self.base_url.endswith("/api/v4"):
            return self._convert_v4(filename=filename, file_bytes=file_bytes)
        return self._convert_legacy(filename=filename, file_bytes=file_bytes)

    def _convert_v4(self, *, filename: str, file_bytes: bytes) -> dict[str, bytes]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "*/*",
        }
        data_id = uuid.uuid4().hex
        apply_payload = {
            "files": [{"name": filename, "data_id": data_id}],
            "model_version": "vlm",
        }

        with httpx.Client(timeout=120, follow_redirects=True, trust_env=False) as client:
            apply_response = client.post(f"{self.base_url}/file-urls/batch", headers=headers, json=apply_payload)
            apply_response.raise_for_status()
            apply_json = apply_response.json()
            if apply_json.get("code") not in (0, "0"):
                raise RuntimeError(f"MineU apply upload url failed: {apply_json.get('msg') or apply_json}")

            apply_data = apply_json.get("data") or {}
            batch_id = apply_data.get("batch_id")
            file_urls = apply_data.get("file_urls") or []
            if not batch_id or not file_urls:
                raise RuntimeError(f"MineU response missing batch_id or file_urls: {apply_json}")

            upload_response = client.put(file_urls[0], content=file_bytes, headers={"Content-Length": str(len(file_bytes))})
            upload_response.raise_for_status()

            last_payload: dict[str, Any] | None = None
            for _ in range(self.max_attempts):
                poll_response = client.get(f"{self.base_url}/extract-results/batch/{batch_id}", headers=headers)
                poll_response.raise_for_status()
                poll_json = poll_response.json()
                if poll_json.get("code") not in (0, "0"):
                    raise RuntimeError(f"MineU poll failed: {poll_json.get('msg') or poll_json}")

                last_payload = poll_json
                result = self._pick_extract_result(poll_json=poll_json, data_id=data_id, filename=filename)
                state = str(result.get("state") or "").lower()
                if state == "done":
                    full_zip_url = result.get("full_zip_url")
                    if not full_zip_url:
                        raise RuntimeError(f"MineU result missing full_zip_url: {poll_json}")
                    zip_response = client.get(full_zip_url)
                    zip_response.raise_for_status()
                    markdown_bytes, json_bytes, asset_files = self._extract_zip_payload(zip_response.content)
                    return {
                        "markdown_bytes": markdown_bytes,
                        "json_bytes": json_bytes,
                        "asset_files": asset_files,
                        "raw_response_bytes": json_dumps(last_payload),
                    }
                if state == "failed":
                    raise RuntimeError(result.get("err_msg") or "MineU extract failed")
                time.sleep(self.poll_seconds)

        raise RuntimeError(f"MineU polling timed out for {filename}")

    def _convert_legacy(self, *, filename: str, file_bytes: bytes) -> dict[str, bytes]:
        request_payload = {"filename": filename}
        files = {"file": (filename, file_bytes, "application/pdf")}
        headers = {"Authorization": f"Bearer {self.api_key}"}

        with httpx.Client(timeout=120, follow_redirects=True, trust_env=False) as client:
            response = client.post(f"{self.base_url}/convert", headers=headers, data=request_payload, files=files)
            response.raise_for_status()
            payload = response.json()

        markdown = payload.get("markdown") or ""
        document_json = payload.get("json") or payload.get("document_json") or {}
        if not markdown or not document_json:
            raise RuntimeError(f"Legacy MineU response missing markdown/json: {payload}")
        return {
            "markdown_bytes": markdown.encode("utf-8"),
            "json_bytes": json.dumps(document_json, ensure_ascii=False, indent=2).encode("utf-8"),
            "asset_files": {},
            "raw_response_bytes": json_dumps(payload),
        }

    @staticmethod
    def _pick_extract_result(*, poll_json: dict[str, Any], data_id: str, filename: str) -> dict[str, Any]:
        data = poll_json.get("data") or {}
        extract_result = data.get("extract_result") or []
        if isinstance(extract_result, dict):
            extract_result = [extract_result]

        for item in extract_result:
            if str(item.get("data_id") or "") == data_id:
                return item
        for item in extract_result:
            if str(item.get("file_name") or "") == filename:
                return item
        if extract_result:
            return extract_result[0]
        raise RuntimeError(f"MineU poll response missing extract_result: {poll_json}")

    @staticmethod
    def _extract_zip_payload(zip_bytes: bytes) -> tuple[bytes, bytes, dict[str, bytes]]:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
            names = archive.namelist()
            markdown_name = next((name for name in names if name.endswith("full.md")), None)
            if markdown_name is None:
                markdown_name = next((name for name in names if name.lower().endswith(".md")), None)
            json_name = next((name for name in names if name.endswith("content_list.json")), None)
            if json_name is None:
                json_name = next((name for name in names if name.lower().endswith(".json")), None)
            if markdown_name is None or json_name is None:
                raise RuntimeError(f"MineU zip missing full.md or json payload: {names}")
            asset_files: dict[str, bytes] = {}
            for name in names:
                normalized_name = name.replace("\\", "/").lstrip("/")
                lower_name = normalized_name.lower()
                if lower_name.endswith("/"):
                    continue
                if not lower_name.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")):
                    continue
                relative_name = MineuService._normalize_asset_name(normalized_name)
                if not relative_name:
                    continue
                asset_files[relative_name] = archive.read(name)
            return archive.read(markdown_name), archive.read(json_name), asset_files

    @staticmethod
    def _normalize_asset_name(name: str) -> str | None:
        normalized = name.replace("\\", "/").lstrip("/")
        lower_name = normalized.lower()
        if "/images/" in lower_name:
            image_offset = lower_name.index("/images/") + 1
            return normalized[image_offset:]
        if lower_name.startswith("images/"):
            return normalized
        filename = normalized.rsplit("/", 1)[-1].strip()
        if not filename:
            return None
        return f"images/{filename}"

    @staticmethod
    def _mock_convert(*, filename: str, job_type: str) -> dict[str, bytes]:
        mock_json = {
            "content_list": [
                {"type": "text", "page": 1, "text": "1. 已知函数f(x)=x^2-2x，求最小值。"},
                {"type": "text", "page": 1, "text": "2. 设数列{an}满足an=n^2，求前n项和。"},
            ]
        }
        markdown = (
            "# 模拟转换结果\n\n"
            f"- 文件：{filename}\n"
            f"- 类型：{job_type}\n\n"
            "1. 已知函数f(x)=x^2-2x，求最小值。\n\n"
            "2. 设数列{an}满足an=n^2，求前n项和。\n"
        )
        raw = {"mode": "mock", "filename": filename, "job_type": job_type}
        return {
            "markdown_bytes": markdown.encode("utf-8"),
            "json_bytes": json.dumps(mock_json, ensure_ascii=False, indent=2).encode("utf-8"),
            "asset_files": {},
            "raw_response_bytes": json_dumps(raw),
        }

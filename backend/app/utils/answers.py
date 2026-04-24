from __future__ import annotations

import json
from typing import Any


def normalize_answer_text_for_markdown(raw_text: str | None) -> str | None:
    if raw_text is None:
        return None
    text = str(raw_text).strip()
    if not text:
        return text
    mapped = _normalize_json_answer_map(text)
    return mapped if mapped is not None else text


def _normalize_json_answer_map(text: str) -> str | None:
    if not (text.startswith("{") and text.endswith("}")):
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or not parsed:
        return None

    rendered_items: list[str] = []
    for key, value in parsed.items():
        answer = _stringify_answer_value(value)
        if not answer:
            continue
        rendered_answer = _wrap_math_answer(answer)
        rendered_items.append(f"{str(key).strip()}. {rendered_answer}")
    return "\n\n".join(rendered_items) if rendered_items else None


def _stringify_answer_value(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return "\n".join(part for part in (_stringify_answer_value(item) for item in value) if part)
    if isinstance(value, dict):
        parts: list[str] = []
        for key, item in value.items():
            rendered = _stringify_answer_value(item)
            if rendered:
                parts.append(f"{key}: {rendered}" if key else rendered)
        return "\n".join(parts)
    return "" if value is None else str(value).strip()


def _wrap_math_answer(answer: str) -> str:
    if "$" in answer:
        return answer
    if "\\" not in answer:
        return answer
    if any("\u4e00" <= char <= "\u9fff" for char in answer):
        return answer
    return f"${answer}$"

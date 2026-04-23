from __future__ import annotations

import re
from collections.abc import Iterable


MATCH_AUTO_APPROVE_CONFIDENCE = 0.93
MIN_COMPLETE_STEM_LENGTH = 12
LOW_CONFIDENCE_NOTE_PATTERN = re.compile(r"^匹配置信度低\s*\((?:0(?:\.\d+)?|1(?:\.0+)?)\)$")
ANALYSIS_FAILURE_NOTE_PREFIX = "题目分析生成失败："
SAME_NUMBER_FALLBACK_NOTE = "LLM 未返回有效候选，已回退到同题号答案"


def split_review_notes(review_note: str | None) -> list[str]:
    if not review_note:
        return []
    return [item.strip() for item in str(review_note).split("；") if item and item.strip()]


def join_review_notes(notes: Iterable[str]) -> str | None:
    unique_notes: list[str] = []
    for note in notes:
        cleaned = str(note or "").strip()
        if cleaned and cleaned not in unique_notes:
            unique_notes.append(cleaned)
    return "；".join(unique_notes) if unique_notes else None


def is_low_confidence_note(note: str | None) -> bool:
    cleaned = str(note or "").strip()
    return bool(cleaned) and bool(LOW_CONFIDENCE_NOTE_PATTERN.match(cleaned))


def is_analysis_failure_note(note: str | None) -> bool:
    return str(note or "").strip().startswith(ANALYSIS_FAILURE_NOTE_PREFIX)


def is_same_number_fallback_note(note: str | None) -> bool:
    return str(note or "").strip() == SAME_NUMBER_FALLBACK_NOTE


def has_complete_stem(stem_text: str | None) -> bool:
    return len(str(stem_text or "").strip()) >= MIN_COMPLETE_STEM_LENGTH


def is_structurally_safe_for_auto_review(
    *,
    stem_text: str | None,
    page_start: int | None,
    has_unique_question_no: bool,
    answer_text: str | None,
) -> bool:
    return bool(
        has_unique_question_no
        and page_start is not None
        and has_complete_stem(stem_text)
        and str(answer_text or "").strip()
    )

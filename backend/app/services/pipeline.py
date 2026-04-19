from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile
from slugify import slugify
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.models import AnswerSheet, ConversionJob, ImportJob, Paper, Question, QuestionAnswer, QuestionKnowledge, QuestionMethod
from app.services.analysis import KnowledgeAnalysisService
from app.services.llm.gateway import LLMGateway
from app.services.mineu.service import MineuService
from app.services.storage.base import FileStorageService
from app.utils.files import build_storage_key, json_dumps, random_prefixed_name, sha256_bytes


QUESTION_START_PATTERN = re.compile(r"^\s*(?:第?\s*)?(\d+)\s*[题、.．)]?\s*(.*)$")
SUBQUESTION_PATTERN = re.compile(r"^\s*[（(]\s*([1-9一二三四五六七八九十])\s*[)）]")
OPTION_PATTERN = re.compile(r"^[A-D][.．、)]")
NOISE_PATTERN = re.compile(r"^\s*(第\s*\d+\s*页(?:\s*共\s*\d+\s*页)?|共\s*\d+\s*页|数学试卷|数学答案|考试时间|满分)\s*$")
SECTION_TITLE_PATTERN = re.compile(r"^[一二三四五六七八九十]+、")
WATERMARK_PATTERN = re.compile(r"^(微信公众号|浙考神墙|QQ[:：]?\s*\d+)")
PREAMBLE_PATTERN = re.compile(
    r"(考生须知|本卷共\d+页|考试时间\d+分钟|答题前|所有答案必须写在答题纸上|考试结束后|只需上交答题纸|准考证号|考场号|座位号)"
)


def question_no_sort_key(question_no: str | None) -> tuple[int, tuple[object, ...]]:
    if not question_no:
        return (1, ("",))
    normalized = str(question_no).strip()
    if not normalized:
        return (1, ("",))
    parts = re.split(r"(\d+)", normalized)
    natural_parts: list[object] = []
    has_digit = False
    for part in parts:
        if not part:
            continue
        if part.isdigit():
            natural_parts.append(int(part))
            has_digit = True
        else:
            natural_parts.append(part)
    return (0 if has_digit else 1, tuple(natural_parts or [normalized]))


@dataclass
class UploadedAsset:
    filename: str
    content: bytes


@dataclass
class NormalizedBlock:
    block_index: int
    page_idx: int | None
    block_type: str
    text: str
    bbox: list[Any] | None
    has_image: bool
    image_src: str | None
    raw: dict[str, Any]


@dataclass
class BoundaryItem:
    candidate_id: str
    question_no: str
    question_type: str
    start_block_index: int
    end_block_index: int
    page_start: int | None
    page_end: int | None
    has_sub_questions: bool
    need_manual_review: bool
    review_reason: str | None = None
    llm_text: str | None = None


@dataclass
class AnswerBoundaryItem:
    candidate_id: str
    answer_question_no: str
    start_block_index: int
    end_block_index: int
    page_start: int | None
    page_end: int | None
    has_sub_questions: bool
    need_manual_review: bool
    review_reason: str | None = None
    llm_text: str | None = None


@dataclass
class QuestionSliceDraft:
    candidate_id: str
    question_no: str
    question_type: str
    stem_text: str
    markdown_excerpt: str
    json_fragment: dict[str, Any]
    page_start: int | None
    page_end: int | None
    image_blocks: list[dict[str, Any]]
    has_sub_questions: bool
    need_manual_review: bool
    review_reason: str | None


@dataclass
class AnswerSliceDraft:
    candidate_id: str
    answer_question_no: str
    stem_text: str
    markdown_excerpt: str
    json_fragment: dict[str, Any]
    page_start: int | None
    page_end: int | None
    image_blocks: list[dict[str, Any]]
    has_sub_questions: bool
    need_manual_review: bool
    review_reason: str | None


def normalize_pair_key(filename: str) -> str:
    stem = Path(filename).stem.lower()
    if "-" in stem:
        stem = stem.split("-", 1)[1]
    normalized = (
        stem.replace("_", "-")
        .replace("（", "(")
        .replace("）", ")")
        .replace(" ", "")
    )
    normalized = re.sub(r"[-—–]+", "-", normalized).strip("-")
    return normalized or stem


class SliceService:
    def coarse_slice(self, document_json: dict[str, Any], markdown_text: str, block_type: str) -> list[dict[str, Any]]:
        blocks = self._normalize_blocks(document_json)
        if not blocks:
            return self._fallback_from_markdown(markdown_text)
        return self._group_blocks(blocks, answer_mode=block_type == "answer")

    def normalize_document(self, document_json: dict[str, Any] | list[dict[str, Any]]) -> list[NormalizedBlock]:
        raw_blocks = self._extract_raw_blocks(document_json)
        blocks: list[NormalizedBlock] = []
        for raw_index, raw in enumerate(raw_blocks):
            expanded_blocks = self._expand_raw_block(raw_index=raw_index, raw=raw)
            blocks.extend(expanded_blocks)
        return blocks

    def detect_question_boundaries(
        self,
        *,
        document_json: dict[str, Any] | list[dict[str, Any]],
        markdown_text: str,
        llm_gateway: LLMGateway,
    ) -> list[BoundaryItem]:
        blocks = self.normalize_document(document_json)
        first_question_section_index = self._find_first_question_section_index(blocks)
        marker_hints = self._collect_question_marker_hints(blocks, first_question_section_index=first_question_section_index)
        payload = {
            "document_type": "paper",
            "blocks": self._compact_blocks_for_llm(blocks, first_question_section_index=first_question_section_index),
            "question_marker_hints": marker_hints,
            "markdown_excerpt": markdown_text[:6000],
        }
        result = llm_gateway.structured_output(scenario="full_paper_boundary", payload=payload)
        items = result.get("items") or []
        if not items and marker_hints:
            retry_payload = {
                **payload,
                "blocks": [block for block in payload["blocks"] if block["has_question_marker"] or block["is_section_title"] or block["has_sub_question_marker"]],
            }
            result = llm_gateway.structured_output(scenario="full_paper_boundary", payload=retry_payload)
            items = result.get("items") or []
        return self._normalize_question_boundaries(
            items=items,
            blocks=blocks,
            first_question_section_index=first_question_section_index,
        )

    def detect_answer_boundaries(
        self,
        *,
        document_json: dict[str, Any] | list[dict[str, Any]],
        markdown_text: str,
        llm_gateway: LLMGateway,
    ) -> list[AnswerBoundaryItem]:
        blocks = self.normalize_document(document_json)
        marker_hints = self._collect_answer_marker_hints(blocks)
        payload = {
            "document_type": "answer",
            "blocks": self._compact_blocks_for_llm(blocks),
            "answer_marker_hints": marker_hints,
            "markdown_excerpt": markdown_text[:6000],
        }
        result = llm_gateway.structured_output(scenario="full_answer_boundary", payload=payload)
        items = result.get("items") or []
        if not items and marker_hints:
            retry_payload = {
                **payload,
                "blocks": [block for block in payload["blocks"] if block["has_question_marker"] or block["type"] in {"table", "image"}],
            }
            result = llm_gateway.structured_output(scenario="full_answer_boundary", payload=retry_payload)
            items = result.get("items") or []
        return self._normalize_answer_boundaries(items=items, blocks=blocks)

    def build_question_slices(
        self,
        *,
        document_json: dict[str, Any] | list[dict[str, Any]],
        boundaries: list[BoundaryItem],
    ) -> list[QuestionSliceDraft]:
        blocks = self.normalize_document(document_json)
        drafts: list[QuestionSliceDraft] = []
        seen_question_nos: dict[str, int] = {}
        for index, item in enumerate(boundaries, start=1):
            selected_blocks = self._blocks_in_range(blocks, item.start_block_index, item.end_block_index) if item.start_block_index >= 0 else []
            stem_text = self._merge_block_texts(selected_blocks) if selected_blocks else str(item.llm_text or "").strip()
            if not stem_text.strip():
                continue
            duplicate_count = seen_question_nos.get(item.question_no, 0)
            seen_question_nos[item.question_no] = duplicate_count + 1
            review_reason = item.review_reason
            need_manual_review = item.need_manual_review
            if duplicate_count:
                need_manual_review = True
                duplicate_reason = f"检测到重复题号 {item.question_no}"
                review_reason = f"{review_reason}；{duplicate_reason}" if review_reason else duplicate_reason
            image_blocks = [self._build_image_ref_from_normalized(block) for block in selected_blocks if block.has_image]
            json_fragment = {
                "candidate_id": item.candidate_id,
                "question_no": item.question_no,
                "blocks": [self._serialize_normalized_block(block) for block in selected_blocks],
                "image_blocks": image_blocks,
                "merged_text": stem_text,
                "review_reason": review_reason,
                "llm_text": item.llm_text,
            }
            drafts.append(
                QuestionSliceDraft(
                    candidate_id=item.candidate_id,
                    question_no=item.question_no,
                    question_type=item.question_type or self._guess_question_type(stem_text),
                    stem_text=stem_text,
                    markdown_excerpt=stem_text,
                    json_fragment=json_fragment,
                    page_start=item.page_start,
                    page_end=item.page_end,
                    image_blocks=image_blocks,
                    has_sub_questions=item.has_sub_questions,
                    need_manual_review=need_manual_review,
                    review_reason=review_reason,
                )
            )
        return drafts

    def build_answer_slices(
        self,
        *,
        document_json: dict[str, Any] | list[dict[str, Any]],
        boundaries: list[AnswerBoundaryItem],
    ) -> list[AnswerSliceDraft]:
        blocks = self.normalize_document(document_json)
        drafts: list[AnswerSliceDraft] = []
        seen_answer_ids: dict[str, int] = {}
        for item in boundaries:
            selected_blocks = self._blocks_in_range(blocks, item.start_block_index, item.end_block_index) if item.start_block_index >= 0 else []
            stem_text = self._merge_block_texts(selected_blocks) if selected_blocks else str(item.llm_text or "").strip()
            if not stem_text.strip():
                continue
            duplicate_count = seen_answer_ids.get(item.answer_question_no, 0)
            seen_answer_ids[item.answer_question_no] = duplicate_count + 1
            review_reason = item.review_reason
            need_manual_review = item.need_manual_review
            if duplicate_count:
                need_manual_review = True
                duplicate_reason = f"检测到重复答案题号 {item.answer_question_no}"
                review_reason = f"{review_reason}；{duplicate_reason}" if review_reason else duplicate_reason
            image_blocks = [self._build_image_ref_from_normalized(block) for block in selected_blocks if block.has_image]
            json_fragment = {
                "candidate_id": item.candidate_id,
                "answer_question_no": item.answer_question_no,
                "blocks": [self._serialize_normalized_block(block) for block in selected_blocks],
                "image_blocks": image_blocks,
                "merged_text": stem_text,
                "review_reason": review_reason,
                "llm_text": item.llm_text,
            }
            drafts.append(
                AnswerSliceDraft(
                    candidate_id=item.candidate_id,
                    answer_question_no=item.answer_question_no,
                    stem_text=stem_text,
                    markdown_excerpt=stem_text,
                    json_fragment=json_fragment,
                    page_start=item.page_start,
                    page_end=item.page_end,
                    image_blocks=image_blocks,
                    has_sub_questions=item.has_sub_questions,
                    need_manual_review=need_manual_review,
                    review_reason=review_reason,
                )
            )
        return drafts

    def _normalize_blocks(self, document_json: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        raw_blocks = self._extract_raw_blocks(document_json)
        blocks: list[dict[str, Any]] = []
        for idx, raw in enumerate(raw_blocks):
            text = (
                raw.get("text")
                or raw.get("content")
                or raw.get("markdown")
                or raw.get("raw_text")
                or raw.get("table_body")
                or raw.get("caption")
                or ""
            ).strip()
            block_type = str(raw.get("type") or raw.get("block_type") or "").lower()
            page = raw.get("page") or raw.get("page_no") or raw.get("page_start") or raw.get("page_index")
            image_src = (
                raw.get("image_url")
                or raw.get("image_path")
                or raw.get("img_path")
                or raw.get("src")
                or raw.get("url")
                or raw.get("oss_url")
            )
            blocks.append(
                {
                    "seq": idx,
                    "text": text,
                    "type": block_type,
                    "page": page,
                    "question_no": raw.get("question_no"),
                    "image_src": image_src,
                    "raw": raw,
                }
            )
        return blocks

    @staticmethod
    def _extract_raw_blocks(document_json: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
        if isinstance(document_json, list):
            return [item for item in document_json if isinstance(item, dict)]
        return [item for item in (document_json.get("blocks") or document_json.get("content_list") or []) if isinstance(item, dict)]

    def _expand_raw_block(self, *, raw_index: int, raw: dict[str, Any]) -> list[NormalizedBlock]:
        block_type = str(raw.get("type") or raw.get("block_type") or "").lower()
        page = raw.get("page") or raw.get("page_no") or raw.get("page_start") or raw.get("page_index") or raw.get("page_idx")
        image_src = (
            raw.get("image_url")
            or raw.get("image_path")
            or raw.get("img_path")
            or raw.get("src")
            or raw.get("url")
            or raw.get("oss_url")
        )
        bbox = raw.get("bbox") or raw.get("position") or raw.get("coordinates")
        items: list[str] = []
        if block_type == "list" and isinstance(raw.get("list_items"), list):
            items = [str(item).strip() for item in raw.get("list_items") if str(item).strip()]
        elif raw.get("table_body"):
            items = [self._strip_html(str(raw.get("table_body") or ""))]
        else:
            items = [
                str(
                    raw.get("text")
                    or raw.get("content")
                    or raw.get("markdown")
                    or raw.get("raw_text")
                    or raw.get("caption")
                    or ""
                ).strip()
            ]

        normalized_blocks: list[NormalizedBlock] = []
        for item_index, text in enumerate(items):
            if not text and not image_src and "image" not in block_type and block_type != "table":
                continue
            block_text = text or "[图片]"
            normalized_type = "list_item" if block_type == "list" else block_type
            if self._should_skip_normalized_block(block_type=normalized_type, text=block_text):
                continue
            normalized_blocks.append(
                NormalizedBlock(
                    block_index=raw_index * 100 + item_index,
                    page_idx=page,
                    block_type=normalized_type or "text",
                    text=block_text,
                    bbox=bbox,
                    has_image=bool(image_src) or "image" in block_type or block_type == "table",
                    image_src=image_src,
                    raw=raw,
                )
            )
        return normalized_blocks

    def _group_blocks(self, blocks: list[dict[str, Any]], *, answer_mode: bool) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        current: dict[str, Any] | None = None

        for block in blocks:
            if self._is_noise(block):
                continue

            detected_no = self._extract_question_no(block["text"]) or str(block.get("question_no") or "").strip()
            is_image = self._is_image_block(block)
            starts_new = bool(detected_no and (current is None or detected_no != current["candidate_no"]))

            if starts_new:
                if current:
                    candidates.append(self._finalize_candidate(current))
                current = self._new_candidate(detected_no)

            if current is None:
                current = self._new_candidate(detected_no or str(len(candidates) + 1))

            current["pages"].add(block.get("page"))
            current["raw_blocks"].append(block["raw"])

            if is_image:
                current["image_blocks"].append(self._build_image_ref(block))
                current["text_parts"].append("[图片]")
                continue

            text = block["text"]
            if not text:
                continue
            if answer_mode and text.startswith("答案"):
                text = re.sub(r"^答案[:：]?\s*", "", text)
            current["text_parts"].append(text)

        if current:
            candidates.append(self._finalize_candidate(current))

        return [candidate for candidate in candidates if candidate["stem_text"]]

    def _new_candidate(self, candidate_no: str) -> dict[str, Any]:
        return {
            "candidate_no": str(candidate_no or "1"),
            "text_parts": [],
            "image_blocks": [],
            "raw_blocks": [],
            "pages": set(),
        }

    def _finalize_candidate(self, current: dict[str, Any]) -> dict[str, Any]:
        text_parts = self._dedupe_text_parts(current["text_parts"])
        stem_text = "\n".join(text_parts).strip()
        pages = [page for page in current["pages"] if page is not None]
        json_fragment = {
            "candidate_no": current["candidate_no"],
            "blocks": current["raw_blocks"],
            "image_blocks": current["image_blocks"],
            "merged_text": stem_text,
        }
        return {
            "candidate_no": current["candidate_no"],
            "question_type": self._guess_question_type(stem_text),
            "stem_text": stem_text,
            "markdown_excerpt": stem_text,
            "page_start": min(pages) if pages else None,
            "page_end": max(pages) if pages else None,
            "json_fragment": json_fragment,
            "block_count": len(current["raw_blocks"]),
            "image_blocks": current["image_blocks"],
        }

    def _fallback_from_markdown(self, markdown_text: str) -> list[dict[str, Any]]:
        chunks: list[dict[str, Any]] = []
        current_no = "1"
        current_lines: list[str] = []

        for raw_line in markdown_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            matched = QUESTION_START_PATTERN.match(line)
            if matched and current_lines:
                chunks.append(self._build_fallback_chunk(current_no, current_lines))
                current_no = matched.group(1)
                current_lines = [matched.group(2).strip() or line]
            else:
                if matched:
                    current_no = matched.group(1)
                    current_lines.append(matched.group(2).strip() or line)
                else:
                    current_lines.append(line)

        if current_lines:
            chunks.append(self._build_fallback_chunk(current_no, current_lines))
        return chunks

    def _build_fallback_chunk(self, candidate_no: str, lines: list[str]) -> dict[str, Any]:
        merged = "\n".join(lines).strip()
        return {
            "candidate_no": candidate_no,
            "question_type": self._guess_question_type(merged),
            "stem_text": merged,
            "markdown_excerpt": merged,
            "page_start": None,
            "page_end": None,
            "json_fragment": {"merged_text": merged, "blocks": [], "image_blocks": []},
            "block_count": 0,
            "image_blocks": [],
        }

    @staticmethod
    def _extract_question_no(text: str) -> str | None:
        if not text:
            return None
        match = QUESTION_START_PATTERN.match(text)
        if match:
            return match.group(1)
        return None

    @staticmethod
    def _is_image_block(block: dict[str, Any]) -> bool:
        return "image" in block["type"] or bool(block.get("image_src"))

    @staticmethod
    def _build_image_ref(block: dict[str, Any]) -> dict[str, Any]:
        raw = block["raw"]
        caption = raw.get("caption") or raw.get("text") or raw.get("content")
        if not caption and isinstance(raw.get("image_caption"), list) and raw["image_caption"]:
            caption = raw["image_caption"][0]
        return {
            "page": block.get("page"),
            "src": block.get("image_src"),
            "caption": caption,
            "bbox": raw.get("bbox") or raw.get("position") or raw.get("coordinates"),
            "type": raw.get("type") or raw.get("block_type") or "image",
        }

    def _build_image_ref_from_normalized(self, block: NormalizedBlock) -> dict[str, Any]:
        caption = block.raw.get("caption") or block.raw.get("text") or block.raw.get("content")
        if not caption and isinstance(block.raw.get("image_caption"), list) and block.raw["image_caption"]:
            caption = block.raw["image_caption"][0]
        if not caption and isinstance(block.raw.get("table_caption"), list) and block.raw["table_caption"]:
            caption = block.raw["table_caption"][0]
        return {
            "page": block.page_idx,
            "src": block.image_src,
            "caption": caption,
            "bbox": block.bbox,
            "type": block.block_type,
        }

    @staticmethod
    def _is_noise(block: dict[str, Any]) -> bool:
        text = block["text"]
        if not text:
            return False
        return bool(NOISE_PATTERN.match(text))

    @staticmethod
    def _strip_html(text: str) -> str:
        cleaned = re.sub(r"<[^>]+>", " ", text)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()

    @staticmethod
    def _should_skip_normalized_block(*, block_type: str, text: str) -> bool:
        normalized = text.strip()
        if not normalized:
            return True
        if block_type in {"page_number", "header", "footer"}:
            return True
        if NOISE_PATTERN.match(normalized):
            return True
        if WATERMARK_PATTERN.match(normalized):
            return True
        if PREAMBLE_PATTERN.search(normalized):
            return True
        return False

    def _compact_blocks_for_llm(
        self,
        blocks: list[NormalizedBlock],
        *,
        first_question_section_index: int | None = None,
    ) -> list[dict[str, Any]]:
        compacted: list[dict[str, Any]] = []
        for block in blocks:
            compacted.append(
                {
                    "block_index": block.block_index,
                    "page_idx": block.page_idx,
                    "type": block.block_type,
                    "text": block.text[:220],
                    "bbox": block.bbox,
                    "has_image": block.has_image,
                    "has_question_marker": bool(self._extract_question_no(block.text)),
                    "has_sub_question_marker": bool(SUBQUESTION_PATTERN.search(block.text)),
                    "is_section_title": bool(SECTION_TITLE_PATTERN.match(block.text)),
                    "is_before_first_question_section": (
                        first_question_section_index is not None and block.block_index < first_question_section_index
                    ),
                }
            )
        return compacted

    def _collect_question_marker_hints(
        self,
        blocks: list[NormalizedBlock],
        *,
        first_question_section_index: int | None = None,
    ) -> list[dict[str, Any]]:
        hints: list[dict[str, Any]] = []
        for block in blocks:
            if not self._extract_question_no(block.text):
                continue
            if first_question_section_index is not None and block.block_index < first_question_section_index:
                continue
            if PREAMBLE_PATTERN.search(block.text) or "注意事项" in block.text:
                continue
            hints.append(
                {
                    "block_index": block.block_index,
                    "page_idx": block.page_idx,
                    "question_no": self._extract_question_no(block.text),
                    "text": block.text[:120],
                }
            )
        return hints[:80]

    @staticmethod
    def _find_first_question_section_index(blocks: list[NormalizedBlock]) -> int | None:
        for block in blocks:
            text = block.text.strip()
            if not SECTION_TITLE_PATTERN.match(text):
                continue
            if any(keyword in text for keyword in ("单选题", "多选题", "填空题", "解答题", "选择题")):
                return block.block_index
        return None

    def _collect_answer_marker_hints(self, blocks: list[NormalizedBlock]) -> list[dict[str, Any]]:
        hints: list[dict[str, Any]] = []
        for block in blocks:
            question_no = self._extract_question_no(block.text)
            if question_no or block.block_type == "table":
                hints.append(
                    {
                        "block_index": block.block_index,
                        "page_idx": block.page_idx,
                        "answer_question_no": question_no,
                        "type": block.block_type,
                        "text": block.text[:120],
                    }
                )
        return hints[:80]

    def _normalize_question_boundaries(
        self,
        *,
        items: list[dict[str, Any]],
        blocks: list[NormalizedBlock],
        first_question_section_index: int | None = None,
    ) -> list[BoundaryItem]:
        valid_indices = {block.block_index for block in blocks}
        boundaries: list[BoundaryItem] = []
        for index, item in enumerate(items, start=1):
            start_index = self._to_int(item.get("start_block_index"))
            end_index = self._to_int(item.get("end_block_index"))
            if start_index is None or end_index is None:
                resolved_range = self._resolve_range_from_question_no(blocks=blocks, question_no=str(item.get("question_no") or ""))
                if resolved_range:
                    start_index, end_index = resolved_range
            if start_index is None or end_index is None:
                if item.get("llm_text"):
                    question_no = str(item.get("question_no") or index).strip() or str(index)
                    boundaries.append(
                        BoundaryItem(
                            candidate_id=f"paper-{index}",
                            question_no=question_no,
                            question_type=str(item.get("question_type") or "解答题"),
                            start_block_index=-1,
                            end_block_index=-1,
                            page_start=self._to_int(item.get("page_start")),
                            page_end=self._to_int(item.get("page_end")),
                            has_sub_questions=bool(item.get("has_sub_questions")),
                            need_manual_review=True,
                            review_reason=str(item.get("review_reason") or "LLM 仅返回结构化题面，未返回可定位边界").strip(),
                            llm_text=str(item.get("llm_text") or "").strip() or None,
                        )
                    )
                continue
            if start_index not in valid_indices or end_index not in valid_indices:
                continue
            if start_index > end_index:
                start_index, end_index = end_index, start_index
            if first_question_section_index is not None and start_index < first_question_section_index:
                continue
            question_no = str(item.get("question_no") or index).strip()
            if not question_no:
                question_no = str(index)
            selected = self._blocks_in_range(blocks, start_index, end_index)
            if not selected:
                continue
            boundaries.append(
                BoundaryItem(
                    candidate_id=f"paper-{index}",
                    question_no=question_no,
                    question_type=str(item.get("question_type") or self._guess_question_type(self._merge_block_texts(selected))),
                    start_block_index=start_index,
                    end_block_index=end_index,
                    page_start=self._first_non_none(item.get("page_start"), selected[0].page_idx),
                    page_end=self._first_non_none(item.get("page_end"), selected[-1].page_idx),
                    has_sub_questions=bool(item.get("has_sub_questions")),
                    need_manual_review=bool(item.get("need_manual_review")),
                    review_reason=str(item.get("review_reason") or "").strip() or None,
                    llm_text=str(item.get("llm_text") or "").strip() or None,
                )
            )
        return boundaries

    def _normalize_answer_boundaries(self, *, items: list[dict[str, Any]], blocks: list[NormalizedBlock]) -> list[AnswerBoundaryItem]:
        valid_indices = {block.block_index for block in blocks}
        boundaries: list[AnswerBoundaryItem] = []
        for index, item in enumerate(items, start=1):
            text_only_candidate = bool(item.get("text_only_candidate"))
            start_index = self._to_int(item.get("start_block_index"))
            end_index = self._to_int(item.get("end_block_index"))
            if text_only_candidate and item.get("llm_text"):
                boundaries.append(
                    AnswerBoundaryItem(
                        candidate_id=f"answer-{index}",
                        answer_question_no=str(item.get("answer_question_no") or item.get("question_no") or index).strip() or str(index),
                        start_block_index=-1,
                        end_block_index=-1,
                        page_start=self._to_int(item.get("page_start")),
                        page_end=self._to_int(item.get("page_end")),
                        has_sub_questions=bool(item.get("has_sub_questions")),
                        need_manual_review=bool(item.get("need_manual_review")),
                        review_reason=str(item.get("review_reason") or "").strip() or None,
                        llm_text=str(item.get("llm_text") or "").strip() or None,
                    )
                )
                continue
            if start_index is None or end_index is None:
                resolved_range = self._resolve_range_from_question_no(
                    blocks=blocks,
                    question_no=str(item.get("answer_question_no") or item.get("question_no") or ""),
                )
                if resolved_range:
                    start_index, end_index = resolved_range
            if start_index is None or end_index is None:
                boundaries.append(
                    AnswerBoundaryItem(
                        candidate_id=f"answer-{index}",
                        answer_question_no=str(item.get("answer_question_no") or item.get("question_no") or index).strip() or str(index),
                        start_block_index=-1,
                        end_block_index=-1,
                        page_start=self._to_int(item.get("page_start")),
                        page_end=self._to_int(item.get("page_end")),
                        has_sub_questions=bool(item.get("has_sub_questions")),
                        need_manual_review=bool(item.get("need_manual_review") or item.get("llm_text")),
                        review_reason=str(item.get("review_reason") or "").strip() or None,
                        llm_text=str(item.get("llm_text") or "").strip() or None,
                    )
                )
                continue
            if start_index not in valid_indices or end_index not in valid_indices:
                continue
            if start_index > end_index:
                start_index, end_index = end_index, start_index
            answer_question_no = str(item.get("answer_question_no") or item.get("question_no") or index).strip()
            if not answer_question_no:
                answer_question_no = str(index)
            selected = self._blocks_in_range(blocks, start_index, end_index)
            if not selected:
                continue
            boundaries.append(
                AnswerBoundaryItem(
                    candidate_id=f"answer-{index}",
                    answer_question_no=answer_question_no,
                    start_block_index=start_index,
                    end_block_index=end_index,
                    page_start=self._first_non_none(item.get("page_start"), selected[0].page_idx),
                    page_end=self._first_non_none(item.get("page_end"), selected[-1].page_idx),
                    has_sub_questions=bool(item.get("has_sub_questions")),
                    need_manual_review=bool(item.get("need_manual_review")),
                    review_reason=str(item.get("review_reason") or "").strip() or None,
                    llm_text=str(item.get("llm_text") or "").strip() or None,
                )
            )
        return boundaries

    def _resolve_range_from_question_no(self, *, blocks: list[NormalizedBlock], question_no: str) -> tuple[int, int] | None:
        if not question_no:
            return None
        start_positions = [
            index
            for index, block in enumerate(blocks)
            if self._extract_question_no(block.text) == question_no and self._is_probable_question_start(block)
        ]
        if not start_positions:
            start_positions = [index for index, block in enumerate(blocks) if self._extract_question_no(block.text) == question_no]
        if not start_positions:
            return None
        start_pos = start_positions[0]
        end_pos = len(blocks) - 1
        for next_pos in range(start_pos + 1, len(blocks)):
            if self._extract_question_no(blocks[next_pos].text) and self._is_probable_question_start(blocks[next_pos]):
                end_pos = next_pos - 1
                break
        return blocks[start_pos].block_index, blocks[end_pos].block_index

    @staticmethod
    def _is_probable_question_start(block: NormalizedBlock) -> bool:
        text = block.text.strip()
        if PREAMBLE_PATTERN.search(text) or "答题时" in text or "注意事项" in text:
            return False
        if WATERMARK_PATTERN.match(text):
            return False
        return True

    @staticmethod
    def _blocks_in_range(blocks: list[NormalizedBlock], start_index: int, end_index: int) -> list[NormalizedBlock]:
        return [block for block in blocks if start_index <= block.block_index <= end_index]

    @staticmethod
    def _merge_block_texts(blocks: list[NormalizedBlock]) -> str:
        return "\n".join(part for part in [block.text.strip() for block in blocks] if part).strip()

    @staticmethod
    def _serialize_normalized_block(block: NormalizedBlock) -> dict[str, Any]:
        return {
            "block_index": block.block_index,
            "page_idx": block.page_idx,
            "type": block.block_type,
            "text": block.text,
            "bbox": block.bbox,
            "img_path": block.image_src,
        }

    @staticmethod
    def _first_non_none(*values: Any) -> Any:
        for value in values:
            if value is not None:
                return value
        return None

    @staticmethod
    def _to_int(value: Any) -> int | None:
        try:
            if value is None or value == "":
                return None
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _dedupe_text_parts(parts: list[str]) -> list[str]:
        cleaned: list[str] = []
        previous = None
        for part in parts:
            normalized = part.strip()
            if not normalized:
                continue
            if normalized == previous:
                continue
            cleaned.append(normalized)
            previous = normalized
        return cleaned

    @staticmethod
    def _guess_question_type(text: str) -> str:
        if not text:
            return "未知"
        if OPTION_PATTERN.search(text):
            return "选择题"
        if "填空" in text:
            return "填空题"
        if SUBQUESTION_PATTERN.search(text):
            return "解答题"
        return "解答题"


class MatchService:
    def __init__(self, llm_gateway: LLMGateway) -> None:
        self.llm_gateway = llm_gateway

    def refine_and_match(
        self,
        *,
        question_candidate: QuestionSliceDraft,
        answer_candidates: list[AnswerSliceDraft],
    ) -> dict[str, Any]:
        ranked_candidates = self._rank_answer_candidates(
            question_no=question_candidate.question_no,
            answer_candidates=answer_candidates,
        )
        answer_index = [
            {
                "answer_candidate_id": candidate.candidate_id,
                "answer_question_no": candidate.answer_question_no,
                "page_start": candidate.page_start,
                "page_end": candidate.page_end,
                "stem_text": candidate.stem_text[:280],
                "has_sub_questions": candidate.has_sub_questions,
                "image_count": len(candidate.image_blocks),
            }
            for candidate in ranked_candidates[:16]
        ]
        payload = {
            "candidate_id": question_candidate.candidate_id,
            "question_no": question_candidate.question_no,
            "question_type": question_candidate.question_type,
            "stem_text": question_candidate.stem_text[:1800],
            "page_start": question_candidate.page_start,
            "page_end": question_candidate.page_end,
            "has_sub_questions": question_candidate.has_sub_questions,
            "image_blocks": question_candidate.image_blocks[:8],
            "answer_candidates": answer_index,
        }
        result = self.llm_gateway.structured_output(scenario="global_answer_match", payload=payload)
        matched_answer_id = str(result.get("matched_answer_candidate_id") or "").strip()
        matched_answer = next((candidate for candidate in ranked_candidates if candidate.candidate_id == matched_answer_id), None)
        exact_candidate = next(
            (candidate for candidate in ranked_candidates if candidate.answer_question_no == question_candidate.question_no),
            None,
        )
        confidence = float(result.get("match_confidence") or 0.0)
        needs_review = bool(result.get("need_manual_review") or question_candidate.need_manual_review)
        review_reason = str(result.get("review_reason") or "").strip() or question_candidate.review_reason
        if not matched_answer:
            if exact_candidate is not None:
                matched_answer = exact_candidate
                matched_answer_id = exact_candidate.candidate_id
                confidence = max(confidence, 0.78 if len(exact_candidate.stem_text.strip()) >= 20 else 0.65)
                needs_review = True
                fallback_reason = "LLM 未返回有效候选，已回退到同题号答案"
                review_reason = f"{review_reason}；{fallback_reason}" if review_reason else fallback_reason
            else:
                confidence = min(confidence, 0.4)
                needs_review = True
                unmatched_reason = "未匹配到答案"
                review_reason = f"{review_reason}；{unmatched_reason}" if review_reason else unmatched_reason
        elif (
            exact_candidate is not None
            and matched_answer.answer_question_no != question_candidate.question_no
            and confidence < 0.9
        ):
            matched_answer = exact_candidate
            matched_answer_id = exact_candidate.candidate_id
            confidence = max(confidence, 0.72 if len(exact_candidate.stem_text.strip()) >= 20 else 0.6)
            needs_review = True
            exact_reason = "LLM 结果与同题号答案冲突，已优先使用同题号候选"
            review_reason = f"{review_reason}；{exact_reason}" if review_reason else exact_reason
        if not question_candidate.stem_text or len(question_candidate.stem_text) < 12:
            needs_review = True
        return {
            "question_no": question_candidate.question_no,
            "question_type": question_candidate.question_type,
            "stem_text": question_candidate.stem_text,
            "has_sub_questions": question_candidate.has_sub_questions,
            "image_refs": question_candidate.image_blocks,
            "matched_answer_candidate_id": matched_answer_id,
            "match_confidence": confidence,
            "need_manual_review": needs_review,
            "matched_answer": matched_answer,
            "review_reason": review_reason,
            "fallback_notice": result.get("_fallback_notice"),
        }

    @staticmethod
    def _rank_answer_candidates(
        *,
        question_no: str,
        answer_candidates: list[AnswerSliceDraft],
    ) -> list[AnswerSliceDraft]:
        def score(candidate: AnswerSliceDraft) -> tuple[int, int, int]:
            same_no = 0 if candidate.answer_question_no == question_no else 1
            numeric_gap = MatchService._question_no_distance(question_no, candidate.answer_question_no)
            content_penalty = 0 if len(candidate.stem_text.strip()) >= 2 else 1
            return (same_no, numeric_gap, content_penalty)

        return sorted(answer_candidates, key=score)

    @staticmethod
    def _question_no_distance(left: str, right: str) -> int:
        if left.isdigit() and right.isdigit():
            return abs(int(left) - int(right))
        return 9999 if left != right else 0


class PaperPipelineService:
    def __init__(
        self,
        db: Session,
        storage: FileStorageService,
        mineu_service: MineuService,
        slice_service: SliceService,
        match_service: MatchService,
    ) -> None:
        self.db = db
        self.storage = storage
        self.mineu_service = mineu_service
        self.slice_service = slice_service
        self.match_service = match_service

    async def ingest_uploads(
        self,
        *,
        paper_file: UploadFile,
        answer_file: UploadFile | None,
        title: str | None,
        source: str | None,
        region: str | None,
        grade_level: str | None,
        term: str | None,
    ) -> Paper:
        paper_asset = UploadedAsset(filename=paper_file.filename or "paper.pdf", content=await paper_file.read())
        answer_asset = None
        if answer_file is not None:
            answer_asset = UploadedAsset(filename=answer_file.filename or "answer.pdf", content=await answer_file.read())
        return self._create_paper_record(
            paper_asset=paper_asset,
            answer_asset=answer_asset,
            title=title,
            source=source,
            region=region,
            grade_level=grade_level,
            term=term,
        )

    async def import_folder_uploads(
        self,
        *,
        paper_files: list[UploadFile],
        answer_files: list[UploadFile],
    ) -> tuple[ImportJob, list[dict[str, Any]]]:
        paper_assets = [UploadedAsset(filename=item.filename or "paper.pdf", content=await item.read()) for item in paper_files]
        answer_assets = [UploadedAsset(filename=item.filename or "answer.pdf", content=await item.read()) for item in answer_files]
        paired = self._pair_assets(paper_assets, answer_assets)
        imported_items: list[dict[str, Any]] = []

        for pair in paired["items"]:
            paper = self._create_paper_record(
                paper_asset=pair["paper"],
                answer_asset=pair.get("answer"),
                title=None,
                source="folder_import",
                region=None,
                grade_level=None,
                term=None,
            )
            imported_items.append(
                {
                    "paper_filename": pair["paper"].filename,
                    "answer_filename": pair["answer"].filename if pair.get("answer") else None,
                    "pair_key": pair["pair_key"],
                    "paper_id": paper.id,
                    "pair_status": "PAIRED" if pair.get("answer") else "MISSING_ANSWER",
                    "has_answer": bool(pair.get("answer")),
                }
            )

        summary = {
            "paired_count": sum(1 for item in imported_items if item["has_answer"]),
            "missing_answer_count": sum(1 for item in imported_items if not item["has_answer"]),
            "orphan_answer_count": len(paired["orphans"]["answer"]),
            "orphan_answers": [item.filename for item in paired["orphans"]["answer"]],
            "conflict_keys": paired["conflict_keys"],
            "paper_count": len(imported_items),
            "items": imported_items,
        }
        import_job = ImportJob(status="COMPLETED", summary_json=json.dumps(summary, ensure_ascii=False))
        self.db.add(import_job)
        self.db.commit()
        self.db.refresh(import_job)
        return import_job, imported_items

    def list_papers(self) -> list[Paper]:
        return self._list_papers(include_deleted=False)

    def list_manage_papers(
        self,
        *,
        keyword: str | None = None,
        year: int | None = None,
        region: str | None = None,
        grade_level: str | None = None,
        term: str | None = None,
        status: str | None = None,
        has_answer: bool | None = None,
        include_deleted: bool = False,
    ) -> list[Paper]:
        stmt = (
            select(Paper)
            .options(
                selectinload(Paper.answer_sheet),
                selectinload(Paper.conversion_jobs),
                selectinload(Paper.questions),
            )
            .order_by(Paper.updated_at.desc())
        )
        if not include_deleted:
            stmt = stmt.where(Paper.is_deleted.is_(False))
        if keyword:
            stmt = stmt.where(Paper.title.contains(keyword))
        if year is not None:
            stmt = stmt.where(Paper.year == year)
        if region:
            stmt = stmt.where(Paper.region == region)
        if grade_level:
            stmt = stmt.where(Paper.grade_level == grade_level)
        if term:
            stmt = stmt.where(Paper.term == term)
        if status:
            stmt = stmt.where(Paper.status == status)
        if has_answer is not None:
            stmt = stmt.join(Paper.answer_sheet).where(AnswerSheet.has_answer.is_(has_answer))
        papers = list(self.db.execute(stmt).scalars())
        self._decorate_papers(papers)
        return papers

    def get_paper(self, paper_id: int, *, include_deleted: bool = True) -> Paper:
        stmt = (
            select(Paper)
            .options(
                selectinload(Paper.answer_sheet),
                selectinload(Paper.conversion_jobs),
                selectinload(Paper.questions).selectinload(Question.answer),
            )
            .where(Paper.id == paper_id)
        )
        if not include_deleted:
            stmt = stmt.where(Paper.is_deleted.is_(False))
        paper = self.db.execute(stmt).scalar_one_or_none()
        if not paper:
            raise HTTPException(status_code=404, detail="Paper not found")
        self._decorate_papers([paper])
        return paper

    def update_paper(self, paper_id: int, payload: dict[str, Any]) -> Paper:
        paper = self.get_paper(paper_id)
        for field in ["title", "year", "source", "grade_level", "region", "term", "status"]:
            value = payload.get(field)
            if value is not None:
                setattr(paper, field, value)

        if payload.get("has_answer") is not None:
            has_answer = bool(payload["has_answer"])
            if paper.answer_sheet is None:
                paper.answer_sheet = AnswerSheet(paper_id=paper.id, has_answer=has_answer, status="READY" if has_answer else "MISSING")
                self.db.add(paper.answer_sheet)
            paper.answer_sheet.has_answer = has_answer
            if not has_answer:
                paper.answer_sheet.status = "MISSING"
                paper.answer_sheet.answer_pdf_path = None
                paper.answer_sheet.answer_pdf_hash = None
            elif paper.answer_sheet.answer_pdf_path:
                paper.answer_sheet.status = "READY"

        self.db.commit()
        return self.get_paper(paper_id)

    async def bind_answer_upload(self, paper_id: int, answer_file: UploadFile) -> Paper:
        paper = self.get_paper(paper_id)
        answer_asset = UploadedAsset(filename=answer_file.filename or "answer.pdf", content=await answer_file.read())
        answer_path = build_storage_key("raw", "unpaired", "answer", filename=random_prefixed_name(answer_asset.filename))
        self.storage.save_file(answer_asset.content, answer_path)

        if paper.answer_sheet is None:
            paper.answer_sheet = AnswerSheet(paper_id=paper.id, has_answer=True, status="READY")
            self.db.add(paper.answer_sheet)

        paper.answer_sheet.answer_pdf_path = answer_path
        paper.answer_sheet.answer_pdf_hash = sha256_bytes(answer_asset.content)
        paper.answer_sheet.has_answer = True
        paper.answer_sheet.status = "READY"
        self.db.commit()
        return self.get_paper(paper_id)

    def unbind_answer(self, paper_id: int) -> Paper:
        paper = self.get_paper(paper_id)
        if paper.answer_sheet is None:
            paper.answer_sheet = AnswerSheet(paper_id=paper.id, has_answer=False, status="MISSING")
            self.db.add(paper.answer_sheet)
        else:
            paper.answer_sheet.answer_pdf_path = None
            paper.answer_sheet.answer_pdf_hash = None
            paper.answer_sheet.has_answer = False
            paper.answer_sheet.status = "MISSING"
        self.db.commit()
        return self.get_paper(paper_id)

    def soft_delete_paper(self, paper_id: int) -> Paper:
        paper = self.get_paper(paper_id)
        paper.is_deleted = True
        paper.deleted_at = datetime.utcnow()
        self.db.commit()
        return self.get_paper(paper_id)

    def restore_paper(self, paper_id: int) -> Paper:
        paper = self.get_paper(paper_id)
        paper.is_deleted = False
        paper.deleted_at = None
        self.db.commit()
        return self.get_paper(paper_id)

    def run_pipeline(self, paper_id: int) -> Paper:
        paper = self.get_paper(paper_id)
        if paper.is_deleted:
            raise HTTPException(status_code=400, detail="Deleted paper cannot run pipeline")

        try:
            paper_job = self._run_conversion_job(paper, "PAPER", paper.paper_pdf_path)
            answer_job = None
            if paper.answer_sheet and paper.answer_sheet.has_answer and paper.answer_sheet.answer_pdf_path:
                answer_job = self._run_conversion_job(paper, "ANSWER", paper.answer_sheet.answer_pdf_path)

            boundary_job = self._get_or_create_job(paper, job_type="BOUNDARY", provider="LLM")
            boundary_job.status = "RUNNING"
            boundary_job.error_message = None
            paper.status = "BOUNDARY_RUNNING"
            self.db.commit()

            question_doc = json.loads(self.storage.read_file(paper_job.json_path).decode("utf-8"))
            question_md = self.storage.read_file(paper_job.markdown_path).decode("utf-8") if paper_job.markdown_path else ""
            question_boundaries = self.slice_service.detect_question_boundaries(
                document_json=question_doc,
                markdown_text=question_md,
                llm_gateway=self.match_service.llm_gateway,
            )
            if not question_boundaries:
                raise HTTPException(status_code=502, detail="LLM 未返回可用的试卷题目边界")
            question_candidates = self.slice_service.build_question_slices(
                document_json=question_doc,
                boundaries=question_boundaries,
            )
            if not question_candidates:
                raise HTTPException(status_code=502, detail="未能根据题目边界回切出有效题目")

            boundary_warnings: list[str] = []
            answer_candidates: list[AnswerSliceDraft] = []
            if answer_job and answer_job.json_path and answer_job.markdown_path:
                answer_doc = json.loads(self.storage.read_file(answer_job.json_path).decode("utf-8"))
                answer_md = self.storage.read_file(answer_job.markdown_path).decode("utf-8")
                try:
                    answer_boundaries = self.slice_service.detect_answer_boundaries(
                        document_json=answer_doc,
                        markdown_text=answer_md,
                        llm_gateway=self.match_service.llm_gateway,
                    )
                    answer_candidates = self.slice_service.build_answer_slices(
                        document_json=answer_doc,
                        boundaries=answer_boundaries,
                    )
                    if not answer_candidates:
                        boundary_warnings.append("答案边界识别未产出有效切片，已按无答案匹配并标待审。")
                except Exception as exc:  # noqa: BLE001
                    boundary_warnings.append(f"答案边界识别失败，已保留题目并标待审: {exc}")

            boundary_job.status = "SUCCESS"
            boundary_job.error_message = " | ".join(boundary_warnings) if boundary_warnings else None
            match_job = self._get_or_create_job(paper, job_type="MATCH", provider="LLM")
            match_job.status = "RUNNING"
            match_job.error_message = None
            paper.status = "MATCH_RUNNING"
            self.db.commit()

            match_warning = self._replace_questions(paper, question_candidates, answer_candidates)
            combined_warning = " | ".join(item for item in [boundary_job.error_message, match_warning] if item)
            self._archive_source_files(paper)
            match_job.status = "SUCCESS"
            match_job.error_message = combined_warning or None
            self.db.commit()
            return self.get_paper(paper_id)
        except HTTPException as exc:
            stage = "BOUNDARY" if paper.status == "BOUNDARY_RUNNING" else "MATCH"
            self._mark_pipeline_failure(paper, stage=stage, detail=str(exc.detail))
            raise
        except SQLAlchemyError as exc:
            self.db.rollback()
            self._mark_pipeline_failure(paper, stage="SYSTEM", detail=f"数据库写入失败: {exc}")
            raise HTTPException(status_code=500, detail=f"Pipeline database failure: {exc}") from exc
        except Exception as exc:  # noqa: BLE001
            stage = "BOUNDARY" if paper.status == "BOUNDARY_RUNNING" else "MATCH"
            self._mark_pipeline_failure(paper, stage=stage, detail=str(exc))
            raise HTTPException(status_code=502, detail=f"Slice/match failed: {exc}") from exc

    def batch_run_pipeline(self, paper_ids: list[int]) -> list[Paper]:
        return [self.run_pipeline(paper_id) for paper_id in paper_ids]

    def get_import_job(self, import_job_id: int) -> ImportJob:
        import_job = self.db.execute(select(ImportJob).where(ImportJob.id == import_job_id)).scalar_one_or_none()
        if not import_job:
            raise HTTPException(status_code=404, detail="Import job not found")
        return import_job

    def _pair_assets(self, paper_assets: list[UploadedAsset], answer_assets: list[UploadedAsset]) -> dict[str, Any]:
        paper_grouped: dict[str, list[UploadedAsset]] = {}
        answer_grouped: dict[str, list[UploadedAsset]] = {}
        for asset in paper_assets:
            paper_grouped.setdefault(normalize_pair_key(asset.filename), []).append(asset)
        for asset in answer_assets:
            answer_grouped.setdefault(normalize_pair_key(asset.filename), []).append(asset)

        conflict_keys = sorted(
            [
                key
                for key in {**paper_grouped, **answer_grouped}.keys()
                if len(paper_grouped.get(key, [])) > 1 or len(answer_grouped.get(key, [])) > 1
            ]
        )
        items: list[dict[str, Any]] = []
        for pair_key, paper_list in paper_grouped.items():
            answer_list = answer_grouped.get(pair_key, [])
            for index, paper_asset in enumerate(paper_list):
                items.append(
                    {
                        "pair_key": pair_key,
                        "paper": paper_asset,
                        "answer": answer_list[index] if index < len(answer_list) else None,
                    }
                )

        orphan_answers: list[UploadedAsset] = []
        for pair_key, answer_list in answer_grouped.items():
            if pair_key not in paper_grouped:
                orphan_answers.extend(answer_list)
            elif len(answer_list) > len(paper_grouped[pair_key]):
                orphan_answers.extend(answer_list[len(paper_grouped[pair_key]) :])
        return {"items": items, "orphans": {"answer": orphan_answers}, "conflict_keys": conflict_keys}

    def _create_paper_record(
        self,
        *,
        paper_asset: UploadedAsset,
        answer_asset: UploadedAsset | None,
        title: str | None,
        source: str | None,
        region: str | None,
        grade_level: str | None,
        term: str | None,
    ) -> Paper:
        paper_meta = self._extract_meta(paper_asset.filename, title)
        paper_key = build_storage_key("raw", "unpaired", "paper", filename=random_prefixed_name(paper_asset.filename))
        self.storage.save_file(paper_asset.content, paper_key)
        paper = Paper(
            title=paper_meta["title"],
            year=paper_meta["year"],
            source=source,
            grade_level=grade_level or paper_meta["grade_level"],
            region=region,
            term=term or paper_meta["term"],
            paper_pdf_path=paper_key,
            paper_pdf_hash=sha256_bytes(paper_asset.content),
            status="RAW",
        )
        self.db.add(paper)
        self.db.flush()

        answer_path = None
        answer_hash = None
        has_answer = False
        if answer_asset:
            answer_path = build_storage_key("raw", "unpaired", "answer", filename=random_prefixed_name(answer_asset.filename))
            self.storage.save_file(answer_asset.content, answer_path)
            answer_hash = sha256_bytes(answer_asset.content)
            has_answer = True
        answer_sheet = AnswerSheet(
            paper_id=paper.id,
            answer_pdf_path=answer_path,
            answer_pdf_hash=answer_hash,
            has_answer=has_answer,
            status="READY" if has_answer else "MISSING",
        )
        self.db.add(answer_sheet)
        self.db.commit()
        return self.get_paper(paper.id)

    def _extract_meta(self, filename: str, fallback_title: str | None = None) -> dict[str, Any]:
        stem = Path(filename).stem
        title = fallback_title or stem
        year = None
        matched_year = re.search(r"(20\d{2}|25\d{2})", stem)
        if matched_year:
            raw_value = matched_year.group(1)
            year = int(raw_value if len(raw_value) == 4 else f"20{raw_value[-2:]}")
        grade = next((item for item in ["高一", "高二", "高三"] if item in stem), None)
        term_value = next((item for item in ["上学期", "下学期", "期中", "期末", "春季", "秋季"] if item in stem), None)
        return {"title": title, "year": year, "grade_level": grade, "term": term_value}

    def _run_conversion_job(self, paper: Paper, job_type: str, source_key: str) -> ConversionJob:
        existing = self._get_existing_job(paper.id, job_type=job_type)
        if existing and existing.status == "SUCCESS" and self._conversion_assets_complete(paper=paper, job=existing):
            return existing

        job = self._get_or_create_job(paper, job_type=job_type, provider="MINEU")
        job.status = "RUNNING"
        job.error_message = None
        paper.status = "MINEU_RUNNING"
        self.db.commit()

        source_bytes = self.storage.read_file(source_key)
        try:
            result = self.mineu_service.convert_pdf(filename=Path(source_key).name, file_bytes=source_bytes, job_type=job_type)
        except Exception as exc:  # noqa: BLE001
            job.status = "FAILED"
            job.error_message = str(exc)
            paper.status = "MINEU_FAILED"
            self.db.commit()
            raise HTTPException(status_code=502, detail=f"MineU conversion failed: {exc}") from exc

        prefix = build_storage_key("mineu", str(paper.id))
        job.markdown_path = build_storage_key(prefix, filename=f"{job_type.lower()}.md")
        job.json_path = build_storage_key(prefix, filename=f"{job_type.lower()}.json")
        job.raw_response_path = build_storage_key(prefix, filename=f"{job_type.lower()}.raw.json")
        self.storage.save_file(result["markdown_bytes"], job.markdown_path)
        self.storage.save_file(result["json_bytes"], job.json_path)
        self.storage.save_file(result["raw_response_bytes"], job.raw_response_path)
        for asset_name, asset_bytes in (result.get("asset_files") or {}).items():
            normalized_name = str(asset_name).replace("\\", "/").lstrip("/")
            asset_key = build_storage_key(prefix, filename=normalized_name)
            self.storage.save_file(asset_bytes, asset_key)
        job.status = "SUCCESS"
        job.error_message = None
        paper.status = "MINEU_DONE"
        self.db.commit()
        self.db.refresh(job)
        return job

    def _conversion_assets_complete(self, *, paper: Paper, job: ConversionJob) -> bool:
        required_paths = [job.markdown_path, job.json_path, job.raw_response_path]
        if any(not path or not self.storage.exists(path) for path in required_paths):
            return False
        if not job.json_path:
            return False
        try:
            document_json = json.loads(self.storage.read_file(job.json_path).decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return False
        blocks = SliceService().normalize_document(document_json)
        image_sources = sorted({block.image_src for block in blocks if block.image_src})
        if not image_sources:
            return True
        prefix = build_storage_key("mineu", str(paper.id))
        for image_src in image_sources:
            asset_key = build_storage_key(prefix, filename=str(image_src).replace("\\", "/").lstrip("/"))
            if not self.storage.exists(asset_key):
                return False
        return True

    def _mark_pipeline_failure(self, paper: Paper, *, stage: str, detail: str) -> None:
        self.db.rollback()
        fresh_paper = self.get_paper(paper.id)
        if stage == "BOUNDARY":
            job = self._get_or_create_job(fresh_paper, job_type="BOUNDARY", provider="LLM")
            job.status = "FAILED"
            job.error_message = detail
            fresh_paper.status = "BOUNDARY_FAILED"
        elif stage == "MATCH":
            job = self._get_or_create_job(fresh_paper, job_type="MATCH", provider="LLM")
            job.status = "FAILED"
            job.error_message = detail
            fresh_paper.status = "MATCH_FAILED"
        elif stage == "MINEU":
            fresh_paper.status = "MINEU_FAILED"
        else:
            fresh_paper.status = "SYSTEM_FAILED"
            system_job = self._get_existing_job(fresh_paper.id, job_type="MATCH")
            if system_job is not None and system_job.status == "RUNNING":
                system_job.status = "FAILED"
                system_job.error_message = detail
        self.db.commit()

    def _get_existing_job(self, paper_id: int, *, job_type: str) -> ConversionJob | None:
        return self.db.execute(
            select(ConversionJob).where(ConversionJob.paper_id == paper_id, ConversionJob.job_type == job_type)
        ).scalar_one_or_none()

    def _get_or_create_job(self, paper: Paper, *, job_type: str, provider: str) -> ConversionJob:
        existing = self._get_existing_job(paper.id, job_type=job_type)
        if existing is not None:
            existing.provider = provider
            return existing

        job = ConversionJob(
            paper_id=paper.id,
            job_type=job_type,
            provider=provider,
            status="PENDING",
            version_no=1,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def _replace_questions(
        self,
        paper: Paper,
        question_candidates: list[QuestionSliceDraft],
        answer_candidates: list[AnswerSliceDraft],
    ) -> str | None:
        pending_found = False
        fallback_notices: list[str] = []
        analysis_warnings: list[str] = []
        for existing_question in paper.questions:
            self.db.query(QuestionMethod).filter(QuestionMethod.question_id == existing_question.id).delete()
            self.db.query(QuestionKnowledge).filter(QuestionKnowledge.question_id == existing_question.id).delete()
            if existing_question.analysis:
                self.db.delete(existing_question.analysis)
            if existing_question.answer:
                self.db.delete(existing_question.answer)
            self.db.delete(existing_question)
        self.db.flush()

        created_question_ids: list[int] = []
        for index, candidate in enumerate(question_candidates, start=1):
            refined = self.match_service.refine_and_match(question_candidate=candidate, answer_candidates=answer_candidates)
            question_no = str(refined.get("question_no") or candidate.question_no or index)
            review_note = self._build_review_note(candidate, refined)
            review_status = "PENDING" if refined["need_manual_review"] else "APPROVED"
            if refined.get("fallback_notice"):
                fallback_notices.append(str(refined["fallback_notice"]))
            duplicate_index = sum(1 for draft in question_candidates[: index - 1] if draft.question_no == question_no)
            folder_suffix = f"_dup{duplicate_index + 1}" if duplicate_index else ""
            folder_name = f"q_{question_no.zfill(3) if question_no.isdigit() else slugify(question_no, separator='_')}{folder_suffix}"
            q_prefix = build_storage_key("slices", str(paper.id), folder_name)

            question_payload = {
                **candidate.json_fragment,
                "image_blocks": candidate.image_blocks,
                "image_refs": refined.get("image_refs") or candidate.image_blocks,
                "has_sub_questions": candidate.has_sub_questions,
            }
            question = Question(
                paper_id=paper.id,
                question_no=question_no,
                question_type=refined.get("question_type") or candidate.question_type,
                stem_text=(refined.get("stem_text") or candidate.stem_text).strip(),
                question_md_path=build_storage_key(q_prefix, filename="question.md"),
                question_json_path=build_storage_key(q_prefix, filename="question.json"),
                page_start=candidate.page_start,
                page_end=candidate.page_end,
                review_status=review_status,
                review_note=review_note,
            )
            if review_status == "PENDING":
                pending_found = True
            self.storage.save_file(question.stem_text.encode("utf-8"), question.question_md_path)
            self.storage.save_file(json_dumps(question_payload), question.question_json_path)
            self.db.add(question)
            self.db.flush()

            matched_answer = refined.get("matched_answer")
            answer = QuestionAnswer(
                question_id=question.id,
                answer_text=matched_answer.stem_text.strip() if matched_answer else None,
                answer_md_path=build_storage_key(q_prefix, filename="answer.md") if matched_answer else None,
                answer_json_path=build_storage_key(q_prefix, filename="answer.json") if matched_answer else None,
                match_confidence=round(float(refined.get("match_confidence") or 0.0), 4),
                match_status="AUTO_MATCHED" if matched_answer else "UNMATCHED",
            )
            if matched_answer:
                answer_payload = {
                    **matched_answer.json_fragment,
                    "image_blocks": matched_answer.image_blocks,
                }
                self.storage.save_file(matched_answer.stem_text.encode("utf-8"), answer.answer_md_path)
                self.storage.save_file(json_dumps(answer_payload), answer.answer_json_path)
            self.db.add(answer)
            created_question_ids.append(question.id)

        self.db.commit()

        analysis_service = KnowledgeAnalysisService(self.db, LLMGateway())
        for question_id in created_question_ids:
            try:
                analysis_service.analyze_question(question_id)
            except Exception as exc:  # noqa: BLE001
                question = self.db.get(Question, question_id)
                if question is not None:
                    note = question.review_note or ""
                    analysis_note = f"题目分析生成失败：{exc}"
                    question.review_note = f"{note}；{analysis_note}".strip("；")
                    self.db.add(question)
                    self.db.commit()
                analysis_warnings.append(f"question_id={question_id}: {exc}")

        paper.status = "REVIEW_PENDING" if pending_found else "SLICED"
        unique_notices = list(dict.fromkeys([*fallback_notices, *analysis_warnings]))
        return " | ".join(unique_notices) if unique_notices else None

    def _build_review_note(self, candidate: QuestionSliceDraft, refined: dict[str, Any]) -> str | None:
        notes: list[str] = []
        confidence = float(refined.get("match_confidence") or 0.0)
        if confidence < 0.75:
            notes.append(f"匹配置信度低 ({confidence:.2f})")
        if not refined.get("matched_answer"):
            notes.append("未匹配到答案")
        if candidate.review_reason:
            notes.append(candidate.review_reason)
        if refined.get("review_reason"):
            notes.append(str(refined["review_reason"]))
        if candidate.page_start is None:
            notes.append("缺少页码定位")
        if len(candidate.stem_text or "") < 12:
            notes.append("题干可能不完整")
        if candidate.image_blocks and not refined.get("image_refs"):
            notes.append("题图归属待确认")
        unique_notes = [item for item in dict.fromkeys(note for note in notes if note).keys()]
        return "；".join(unique_notes) if unique_notes else None

    def _archive_source_files(self, paper: Paper) -> None:
        if paper.paper_pdf_path.startswith("raw/unpaired/paper"):
            archived_paper = paper.paper_pdf_path.replace("raw/unpaired/paper", "raw/archived/paper")
            paper.paper_pdf_path = self.storage.move_file(paper.paper_pdf_path, archived_paper)
        if paper.answer_sheet and paper.answer_sheet.answer_pdf_path and paper.answer_sheet.answer_pdf_path.startswith(
            "raw/unpaired/answer"
        ):
            archived_answer = paper.answer_sheet.answer_pdf_path.replace("raw/unpaired/answer", "raw/archived/answer")
            paper.answer_sheet.answer_pdf_path = self.storage.move_file(paper.answer_sheet.answer_pdf_path, archived_answer)
            paper.answer_sheet.status = "ARCHIVED"
        elif paper.answer_sheet and not paper.answer_sheet.has_answer:
            paper.answer_sheet.status = "MISSING"

    def _list_papers(self, *, include_deleted: bool) -> list[Paper]:
        stmt = (
            select(Paper)
            .options(
                selectinload(Paper.answer_sheet),
                selectinload(Paper.conversion_jobs),
                selectinload(Paper.questions),
            )
            .order_by(Paper.created_at.desc())
        )
        if not include_deleted:
            stmt = stmt.where(Paper.is_deleted.is_(False))
        papers = list(self.db.execute(stmt).scalars())
        self._decorate_papers(papers)
        return papers

    def _decorate_papers(self, papers: list[Paper]) -> None:
        for paper in papers:
            paper.questions = sorted(
                paper.questions,
                key=lambda question: (question_no_sort_key(question.question_no), question.id),
            )
            setattr(paper, "pending_review_count", sum(1 for question in paper.questions if question.review_status == "PENDING"))
            latest_error = next((job.error_message for job in reversed(paper.conversion_jobs) if job.error_message), None)
            setattr(paper, "latest_error_message", latest_error)
            timestamps = [job.updated_at for job in paper.conversion_jobs if job.updated_at]
            setattr(paper, "last_pipeline_at", max(timestamps) if timestamps else None)

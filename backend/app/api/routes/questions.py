from __future__ import annotations

import json
from pathlib import PurePosixPath
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.db.session import get_db
from app.models import Paper, Question, QuestionAnalysis, QuestionKnowledge, QuestionMethod
from app.schemas.question import QuestionDetailResponse, QuestionTagUpdateRequest
from app.services.review import ReviewService
from app.services.storage.base import FileStorageService
from app.services.storage.factory import get_storage_service

router = APIRouter()


def _build_question_detail_response_payload(question: Question, *, assets: dict[str, object]) -> dict[str, object]:
    answer_payload = None
    if question.answer is not None:
        answer_payload = {
            "created_at": question.answer.created_at,
            "updated_at": question.answer.updated_at,
            "id": question.answer.id,
            "answer_text": question.answer.answer_text,
            "answer_md_path": question.answer.answer_md_path,
            "answer_json_path": question.answer.answer_json_path,
            "match_confidence": float(question.answer.match_confidence) if question.answer.match_confidence is not None else None,
            "match_status": question.answer.match_status,
        }

    analysis_payload = None
    if question.analysis is not None:
        analysis_payload = {
            "created_at": question.analysis.created_at,
            "updated_at": question.analysis.updated_at,
            "id": question.analysis.id,
            "analysis_json": question.analysis.analysis_json,
            "explanation_md": question.analysis.explanation_md,
            "model_name": question.analysis.model_name,
            "version_no": question.analysis.version_no,
            "review_status": question.analysis.review_status,
        }

    return {
        "created_at": question.created_at,
        "updated_at": question.updated_at,
        "id": question.id,
        "paper_id": question.paper_id,
        "question_no": question.question_no,
        "question_type": question.question_type,
        "stem_text": question.stem_text,
        "question_md_path": question.question_md_path,
        "question_json_path": question.question_json_path,
        "page_start": question.page_start,
        "page_end": question.page_end,
        "review_status": question.review_status,
        "review_note": question.review_note,
        "answer": answer_payload,
        "analysis": analysis_payload,
        "knowledges": [link.knowledge_point for link in question.knowledges if link.knowledge_point],
        "methods": [link.solution_method for link in question.methods if link.solution_method],
        "assets": assets,
    }


def _build_file_url(request: Request, storage_key: str) -> str:
    normalized_key = storage_key.replace("\\", "/").lstrip("/")
    if settings.file_service_base_url:
        return f"{settings.file_service_base_url.rstrip('/')}/{quote(normalized_key, safe='/')}"
    return str(request.base_url).rstrip("/") + f"/api/files/{quote(normalized_key, safe='/')}"


def _build_candidate_keys(base_key: str | None, raw_src: str | None) -> list[str]:
    if not raw_src:
        return []
    normalized_src = raw_src.replace("\\", "/").lstrip("/")
    candidates: list[str] = [normalized_src]
    if base_key:
        base_path = PurePosixPath(base_key.replace("\\", "/").lstrip("/"))
        base_dir = base_path.parent
        candidates.append(str(base_dir / normalized_src))
        if base_dir.parts[:1] == ("slices",) and len(base_dir.parts) >= 2:
            candidates.append(str(PurePosixPath("mineu") / base_dir.parts[1] / normalized_src))
    unique_candidates: list[str] = []
    for candidate in candidates:
        if candidate not in unique_candidates:
            unique_candidates.append(candidate)
    return unique_candidates


def _enrich_image_item(
    storage: FileStorageService,
    request: Request,
    base_key: str | None,
    image: dict,
) -> dict:
    payload = dict(image)
    raw_src = payload.get("src") or payload.get("img_path") or payload.get("image_path")
    for candidate in _build_candidate_keys(base_key, raw_src):
        if storage.exists(candidate):
            payload["src"] = _build_file_url(request, candidate)
            payload["storage_key"] = candidate
            payload["status"] = "ready"
            return payload
    if raw_src:
        payload["storage_key"] = _build_candidate_keys(base_key, raw_src)[0]
        payload["status"] = "missing"
    else:
        payload["status"] = "missing"
    payload["src"] = None
    return payload


def _extract_images_from_document(
    storage: FileStorageService,
    request: Request,
    base_key: str | None,
    document_json: dict | None,
) -> list[dict]:
    if not document_json:
        return []

    block_images: list[dict] = []
    for block in document_json.get("blocks") or []:
        block_type = str(block.get("type") or block.get("block_type") or "").lower()
        if "image" not in block_type:
            continue
        caption = block.get("caption") or block.get("text") or block.get("content")
        if not caption and isinstance(block.get("image_caption"), list) and block["image_caption"]:
            caption = block["image_caption"][0]
        block_images.append(
            {
                "page": block.get("page") or block.get("page_idx") or block.get("page_no"),
                "src": block.get("src") or block.get("img_path") or block.get("image_path") or block.get("image_url"),
                "caption": caption,
                "bbox": block.get("bbox") or block.get("position") or block.get("coordinates"),
                "type": block.get("type") or block.get("block_type") or "image",
            }
        )

    refs = [dict(item) for item in (document_json.get("image_refs") or document_json.get("image_blocks") or [])]
    if refs:
        for ref in refs:
            if ref.get("src"):
                continue
            matched_block = next(
                (
                    block_image
                    for block_image in block_images
                    if block_image.get("bbox") == ref.get("bbox")
                    and (ref.get("page") is None or block_image.get("page") == ref.get("page"))
                ),
                None,
            )
            if not matched_block:
                matched_block = next((block_image for block_image in block_images if block_image.get("bbox") == ref.get("bbox")), None)
            if matched_block:
                ref["src"] = matched_block.get("src")
                ref["caption"] = ref.get("caption") or matched_block.get("caption")
                ref["page"] = ref.get("page") if ref.get("page") is not None else matched_block.get("page")
    else:
        refs = block_images

    return [_enrich_image_item(storage, request, base_key, item) for item in refs]


@router.get("/{question_id}", response_model=QuestionDetailResponse)
def get_question(question_id: int, request: Request, db: Session = Depends(get_db)):
    ReviewService(db, get_storage_service()).maintain_review_state(question_id=question_id)
    question = db.execute(
        select(Question)
        .options(
            selectinload(Question.answer),
            selectinload(Question.analysis),
            selectinload(Question.knowledges).selectinload(QuestionKnowledge.knowledge_point),
            selectinload(Question.methods).selectinload(QuestionMethod.solution_method),
            selectinload(Question.paper).selectinload(Paper.answer_sheet),
        )
        .where(Question.id == question_id)
    ).scalar_one_or_none()
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    storage = get_storage_service()
    assets = {
        "question_md": storage.read_file(question.question_md_path).decode("utf-8") if question.question_md_path else None,
        "question_json": json.loads(storage.read_file(question.question_json_path).decode("utf-8"))
        if question.question_json_path
        else None,
    }
    assets["question_images"] = _extract_images_from_document(storage, request, question.question_json_path, assets["question_json"])
    assets["paper_pdf_path"] = question.paper.paper_pdf_path if question.paper else None
    assets["paper_pdf_url"] = None
    if question.paper and question.paper.paper_pdf_path and storage.exists(question.paper.paper_pdf_path):
        assets["paper_pdf_url"] = _build_file_url(request, question.paper.paper_pdf_path)
    if question.answer and question.answer.answer_md_path:
        assets["answer_md"] = storage.read_file(question.answer.answer_md_path).decode("utf-8")
    if question.answer and question.answer.answer_json_path:
        assets["answer_json"] = json.loads(storage.read_file(question.answer.answer_json_path).decode("utf-8"))
        assets["answer_images"] = _extract_images_from_document(
            storage,
            request,
            question.answer.answer_json_path,
            assets["answer_json"],
        )
    assets["answer_pdf_path"] = question.paper.answer_sheet.answer_pdf_path if question.paper and question.paper.answer_sheet else None
    assets["answer_pdf_url"] = None
    if (
        question.paper
        and question.paper.answer_sheet
        and question.paper.answer_sheet.answer_pdf_path
        and storage.exists(question.paper.answer_sheet.answer_pdf_path)
    ):
        assets["answer_pdf_url"] = _build_file_url(request, question.paper.answer_sheet.answer_pdf_path)

    payload = _build_question_detail_response_payload(question, assets=assets)
    return QuestionDetailResponse(**payload)


@router.patch("/{question_id}/tags", response_model=QuestionDetailResponse)
def update_question_tags(
    question_id: int,
    payload: QuestionTagUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    question = db.execute(
        select(Question)
        .options(
            selectinload(Question.answer),
            selectinload(Question.analysis),
            selectinload(Question.knowledges).selectinload(QuestionKnowledge.knowledge_point),
            selectinload(Question.methods).selectinload(QuestionMethod.solution_method),
            selectinload(Question.paper).selectinload(Paper.answer_sheet),
        )
        .where(Question.id == question_id)
    ).scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    knowledge_ids = list(dict.fromkeys(payload.knowledge_point_ids))
    method_ids = list(dict.fromkeys(payload.solution_method_ids))
    db.query(QuestionKnowledge).filter(QuestionKnowledge.question_id == question.id).delete()
    db.query(QuestionMethod).filter(QuestionMethod.question_id == question.id).delete()

    for knowledge_id in knowledge_ids:
        db.add(
            QuestionKnowledge(
                question_id=question.id,
                knowledge_point_id=knowledge_id,
                source_type="MANUAL",
                confidence=1.0,
            )
        )
    for method_id in method_ids:
        db.add(
            QuestionMethod(
                question_id=question.id,
                solution_method_id=method_id,
                source_type="MANUAL",
                confidence=1.0,
            )
        )

    if question.analysis is not None:
        analysis_payload = json.loads(question.analysis.analysis_json or "{}")
        analysis_payload["major_knowledge_points"] = []
        analysis_payload["minor_knowledge_points"] = []
        analysis_payload["solution_methods"] = []
        question.analysis.analysis_json = json.dumps(analysis_payload, ensure_ascii=False)
        question.analysis.review_status = "APPROVED"
        db.add(question.analysis)

    db.commit()

    refreshed = db.execute(
        select(Question)
        .options(
            selectinload(Question.answer),
            selectinload(Question.analysis),
            selectinload(Question.knowledges).selectinload(QuestionKnowledge.knowledge_point),
            selectinload(Question.methods).selectinload(QuestionMethod.solution_method),
            selectinload(Question.paper).selectinload(Paper.answer_sheet),
        )
        .where(Question.id == question_id)
    ).scalar_one()

    if refreshed.analysis is not None:
        analysis_payload = json.loads(refreshed.analysis.analysis_json or "{}")
        analysis_payload["major_knowledge_points"] = [
            link.knowledge_point.name for link in refreshed.knowledges if link.knowledge_point and link.knowledge_point.level == 1
        ]
        analysis_payload["minor_knowledge_points"] = [
            link.knowledge_point.name for link in refreshed.knowledges if link.knowledge_point and link.knowledge_point.level != 1
        ]
        analysis_payload["solution_methods"] = [
            link.solution_method.name for link in refreshed.methods if link.solution_method
        ]
        refreshed.analysis.analysis_json = json.dumps(analysis_payload, ensure_ascii=False)
        db.add(refreshed.analysis)
        db.commit()
        db.refresh(refreshed.analysis)

    storage = get_storage_service()
    assets = {
        "question_md": storage.read_file(refreshed.question_md_path).decode("utf-8") if refreshed.question_md_path else None,
        "question_json": json.loads(storage.read_file(refreshed.question_json_path).decode("utf-8"))
        if refreshed.question_json_path
        else None,
    }
    assets["question_images"] = _extract_images_from_document(storage, request, refreshed.question_json_path, assets["question_json"])
    assets["paper_pdf_path"] = refreshed.paper.paper_pdf_path if refreshed.paper else None
    assets["paper_pdf_url"] = None
    if refreshed.paper and refreshed.paper.paper_pdf_path and storage.exists(refreshed.paper.paper_pdf_path):
        assets["paper_pdf_url"] = _build_file_url(request, refreshed.paper.paper_pdf_path)
    if refreshed.answer and refreshed.answer.answer_md_path:
        assets["answer_md"] = storage.read_file(refreshed.answer.answer_md_path).decode("utf-8")
    if refreshed.answer and refreshed.answer.answer_json_path:
        assets["answer_json"] = json.loads(storage.read_file(refreshed.answer.answer_json_path).decode("utf-8"))
        assets["answer_images"] = _extract_images_from_document(
            storage,
            request,
            refreshed.answer.answer_json_path,
            assets["answer_json"],
        )
    assets["answer_pdf_path"] = refreshed.paper.answer_sheet.answer_pdf_path if refreshed.paper and refreshed.paper.answer_sheet else None
    assets["answer_pdf_url"] = None
    if (
        refreshed.paper
        and refreshed.paper.answer_sheet
        and refreshed.paper.answer_sheet.answer_pdf_path
        and storage.exists(refreshed.paper.answer_sheet.answer_pdf_path)
    ):
        assets["answer_pdf_url"] = _build_file_url(request, refreshed.paper.answer_sheet.answer_pdf_path)
    return QuestionDetailResponse(**_build_question_detail_response_payload(refreshed, assets=assets))

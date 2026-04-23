from __future__ import annotations

import json
import re

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload
from slugify import slugify

from app.models import ChatMessage, ChatSession, Paper, Question, QuestionAnalysis, QuestionAnswer, QuestionKnowledge, QuestionMethod, ReviewRecord
from app.schemas.question import QuestionCreateRequest, QuestionDetailResponse, QuestionUpdateRequest, ReviewQueueItem, ReviewUpdateRequest
from app.services.review_state import (
    MATCH_AUTO_APPROVE_CONFIDENCE,
    is_analysis_failure_note,
    is_low_confidence_note,
    is_same_number_fallback_note,
    is_structurally_safe_for_auto_review,
    join_review_notes,
    split_review_notes,
)
from app.services.storage.base import FileStorageService
from app.utils.files import build_storage_key, json_dumps


class ReviewService:
    def __init__(self, db: Session, storage: FileStorageService) -> None:
        self.db = db
        self.storage = storage

    def maintain_review_state(self, *, question_id: int | None = None) -> int:
        duplicate_keys = {
            (paper_id, question_no)
            for paper_id, question_no, count in self.db.execute(
                select(Question.paper_id, Question.question_no, func.count(Question.id))
                .group_by(Question.paper_id, Question.question_no)
            ).all()
            if count > 1
        }
        stmt = select(Question).options(selectinload(Question.answer), selectinload(Question.analysis))
        if question_id is not None:
            stmt = stmt.where(Question.id == question_id)
        else:
            stmt = stmt.where(or_(Question.review_status == "PENDING", Question.review_note.is_not(None)))
        questions = list(self.db.execute(stmt).scalars())
        updated = 0
        for question in questions:
            if self._maintain_single_question_review_state(question, duplicate_keys=duplicate_keys):
                updated += 1
        if updated:
            self.db.commit()
        return updated

    def create_question(self, paper_id: int, payload: QuestionCreateRequest) -> Question:
        paper = self._get_paper(paper_id)
        question = Question(
            paper_id=paper.id,
            question_no=payload.question_no.strip(),
            question_type=(payload.question_type or "").strip() or None,
            stem_text=payload.stem_text.strip(),
            page_start=payload.page_start,
            page_end=payload.page_end,
            review_status=payload.review_status or "PENDING",
            review_note=payload.review_note,
        )
        self.db.add(question)
        self.db.flush()

        answer_text = (payload.answer_text or "").strip()
        if answer_text:
            answer = QuestionAnswer(
                question_id=question.id,
                answer_text=answer_text,
                match_status="MANUAL_FIXED",
                match_confidence=1.0,
            )
            self.db.add(answer)
        self.db.flush()

        self._sync_paper_question_files(paper.id)
        self.db.commit()
        return self._load_question(question.id)

    def update_question(self, question_id: int, payload: ReviewUpdateRequest) -> Question:
        question = self._load_question(question_id)
        before = {
            "question_no": question.question_no,
            "question_type": question.question_type,
            "stem_text": question.stem_text,
            "answer_text": question.answer.answer_text if question.answer else None,
            "match_status": question.answer.match_status if question.answer else None,
            "review_status": question.review_status,
            "review_note": question.review_note,
            "page_start": question.page_start,
            "page_end": question.page_end,
        }
        if payload.question_no is not None:
            question.question_no = payload.question_no.strip()
        if payload.question_type is not None:
            question.question_type = payload.question_type.strip() or None
        if payload.stem_text is not None:
            question.stem_text = payload.stem_text
        if payload.review_note is not None:
            question.review_note = payload.review_note
        if payload.page_start is not None:
            question.page_start = payload.page_start
        if payload.page_end is not None:
            question.page_end = payload.page_end
        question.review_status = payload.review_status

        if payload.answer_text is not None:
            answer_text = payload.answer_text.strip()
            if answer_text:
                if question.answer is None:
                    question.answer = QuestionAnswer(question_id=question.id, match_status="MANUAL_FIXED", match_confidence=1.0)
                    self.db.add(question.answer)
                question.answer.answer_text = answer_text
                question.answer.match_status = payload.match_status or "MANUAL_FIXED"
                question.answer.match_confidence = 1.0 if question.answer.match_status == "MANUAL_FIXED" else question.answer.match_confidence
            elif question.answer is not None:
                self._delete_answer_record(question.answer)
        elif question.answer and payload.match_status is not None:
            question.answer.match_status = payload.match_status
            if payload.match_status == "MANUAL_FIXED":
                question.answer.match_confidence = 1.0

        review = ReviewRecord(
            paper_id=question.paper_id,
            question_id=question.id,
            review_type=payload.review_type,
            before_data_json=json.dumps(before, ensure_ascii=False),
            after_data_json=json.dumps(payload.model_dump(), ensure_ascii=False),
            comment=payload.comment,
            reviewer_id=payload.reviewer_id,
        )
        self.db.add(review)
        self.db.flush()
        self._sync_paper_question_files(question.paper_id)
        self.db.commit()
        return self._load_question(question.id)

    def patch_question(self, paper_id: int, question_id: int, payload: QuestionUpdateRequest) -> Question:
        review_payload = ReviewUpdateRequest(
            question_no=payload.question_no,
            question_type=payload.question_type,
            stem_text=payload.stem_text,
            answer_text=payload.answer_text,
            match_status="MANUAL_FIXED" if payload.answer_text and payload.answer_text.strip() else None,
            review_status=payload.review_status or "PENDING",
            review_note=payload.review_note,
            page_start=payload.page_start,
            page_end=payload.page_end,
            review_type="SLICE_EDIT",
            comment="通过试卷切片结果列表编辑题目",
        )
        question = self.update_question(question_id, review_payload)
        if question.paper_id != paper_id:
            raise HTTPException(status_code=404, detail="Question not found in target paper")
        return question

    def delete_question(self, paper_id: int, question_id: int) -> None:
        question = self._load_question(question_id)
        if question.paper_id != paper_id:
            raise HTTPException(status_code=404, detail="Question not found in target paper")

        cleanup_paths = self._collect_question_paths(question)
        self.db.query(QuestionMethod).filter(QuestionMethod.question_id == question.id).delete()
        self.db.query(QuestionKnowledge).filter(QuestionKnowledge.question_id == question.id).delete()
        if question.analysis is not None:
            self.db.delete(question.analysis)
        if question.answer is not None:
            self._delete_answer_record(question.answer)
        for session in question.chat_sessions:
            self.db.query(ChatMessage).filter(ChatMessage.session_id == session.id).delete()
            self.db.delete(session)
        for review in question.reviews:
            review.question_id = None
            self.db.add(review)
        self.db.delete(question)
        self.db.flush()
        self._sync_paper_question_files(paper_id, extra_cleanup_paths=cleanup_paths)
        self.db.commit()

    def review_queue(
        self,
        *,
        paper_id: int | None = None,
        review_status: str | None = "PENDING",
        has_answer: bool | None = None,
        include_deleted: bool = False,
    ) -> list[ReviewQueueItem]:
        self.maintain_review_state()
        stmt = (
            select(Question, Paper)
            .join(Paper, Paper.id == Question.paper_id)
            .options(selectinload(Question.answer))
            .order_by(Question.updated_at.desc())
        )
        if paper_id is not None:
            stmt = stmt.where(Question.paper_id == paper_id)
        if review_status:
            stmt = stmt.where(Question.review_status == review_status)
        if not include_deleted:
            stmt = stmt.where(Paper.is_deleted.is_(False))

        rows = self.db.execute(stmt).all()
        items: list[ReviewQueueItem] = []
        for question, paper in rows:
            answer_exists = bool(question.answer and question.answer.answer_text)
            if has_answer is not None and answer_exists is not has_answer:
                continue
            items.append(
                ReviewQueueItem(
                    question_id=question.id,
                    paper_id=paper.id,
                    paper_title=paper.title,
                    question_no=question.question_no,
                    stem_text=question.stem_text,
                    review_status=question.review_status,
                    review_note=question.review_note,
                    match_confidence=float(question.answer.match_confidence) if question.answer and question.answer.match_confidence is not None else None,
                    has_answer=answer_exists,
                )
            )
        items.sort(key=lambda item: (item.match_confidence or 0.0, item.paper_id, item.question_id))
        return items

    def build_question_detail_response(self, question_id: int) -> QuestionDetailResponse:
        self.maintain_review_state(question_id=question_id)
        question = self._load_question(question_id)
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
        return QuestionDetailResponse(
            created_at=question.created_at,
            updated_at=question.updated_at,
            id=question.id,
            paper_id=question.paper_id,
            question_no=question.question_no,
            question_type=question.question_type,
            stem_text=question.stem_text,
            question_md_path=question.question_md_path,
            question_json_path=question.question_json_path,
            page_start=question.page_start,
            page_end=question.page_end,
            review_status=question.review_status,
            review_note=question.review_note,
            answer=answer_payload,
            analysis=analysis_payload,
            knowledges=[link.knowledge_point for link in question.knowledges if link.knowledge_point],
            methods=[link.solution_method for link in question.methods if link.solution_method],
            assets={},
        )

    def _get_paper(self, paper_id: int) -> Paper:
        paper = self.db.execute(select(Paper).where(Paper.id == paper_id)).scalar_one_or_none()
        if paper is None:
            raise HTTPException(status_code=404, detail="Paper not found")
        return paper

    def _load_question(self, question_id: int) -> Question:
        question = self.db.execute(
            select(Question)
            .options(
                selectinload(Question.answer),
                selectinload(Question.analysis),
                selectinload(Question.knowledges).selectinload(QuestionKnowledge.knowledge_point),
                selectinload(Question.methods).selectinload(QuestionMethod.solution_method),
                selectinload(Question.reviews),
                selectinload(Question.chat_sessions).selectinload(ChatSession.messages),
            )
            .where(Question.id == question_id)
        ).scalar_one()
        return question

    def _load_questions_for_paper(self, paper_id: int) -> list[Question]:
        return list(
            self.db.execute(
                select(Question)
                .options(selectinload(Question.answer))
                .where(Question.paper_id == paper_id)
                .order_by(Question.id.asc())
            ).scalars()
        )

    def _sync_paper_question_files(self, paper_id: int, *, extra_cleanup_paths: list[str] | None = None) -> None:
        cleanup_paths = set(extra_cleanup_paths or [])
        questions = self._load_questions_for_paper(paper_id)
        folder_names = self._build_folder_names(questions)
        new_paths: set[str] = set()

        for question in questions:
            cleanup_paths.update(self._collect_question_paths(question))
            q_prefix = build_storage_key("slices", str(paper_id), folder_names[question.id])

            question.question_md_path = build_storage_key(q_prefix, filename="question.md")
            question.question_json_path = build_storage_key(q_prefix, filename="question.json")
            question_payload = self._build_question_payload(question)
            self.storage.save_file(question.stem_text.encode("utf-8"), question.question_md_path)
            self.storage.save_file(json_dumps(question_payload), question.question_json_path)
            new_paths.update([question.question_md_path, question.question_json_path])

            if question.answer is not None and (question.answer.answer_text or "").strip():
                question.answer.answer_md_path = build_storage_key(q_prefix, filename="answer.md")
                question.answer.answer_json_path = build_storage_key(q_prefix, filename="answer.json")
                answer_payload = self._build_answer_payload(question.answer)
                self.storage.save_file(question.answer.answer_text.encode("utf-8"), question.answer.answer_md_path)
                self.storage.save_file(json_dumps(answer_payload), question.answer.answer_json_path)
                new_paths.update([question.answer.answer_md_path, question.answer.answer_json_path])
            elif question.answer is not None:
                cleanup_paths.update(path for path in [question.answer.answer_md_path, question.answer.answer_json_path] if path)
                question.answer.answer_md_path = None
                question.answer.answer_json_path = None

        duplicate_numbers = {item.question_no for item in questions if sum(1 for row in questions if row.question_no == item.question_no) > 1}
        for question in questions:
            duplicate_note = f"重复题号 {question.question_no}"
            if question.question_no in duplicate_numbers:
                question.review_status = "PENDING"
                existing_note = question.review_note or ""
                if duplicate_note not in existing_note:
                    question.review_note = f"{existing_note}；{duplicate_note}".strip("；")
            elif question.review_note and duplicate_note in question.review_note:
                cleaned_note = re.sub(rf"(?:^|；){re.escape(duplicate_note)}(?:；|$)", "；", question.review_note).strip("；")
                question.review_note = cleaned_note or None

        for path in cleanup_paths:
            if path and path not in new_paths and self.storage.exists(path):
                self.storage.delete_file(path)
        self.db.flush()

    def _maintain_single_question_review_state(
        self,
        question: Question,
        *,
        duplicate_keys: set[tuple[int, str]],
    ) -> bool:
        original_note = question.review_note
        original_status = question.review_status
        original_confidence = (
            float(question.answer.match_confidence)
            if question.answer and question.answer.match_confidence is not None
            else None
        )

        actionable_notes: list[str] = []
        match_noise_notes: list[str] = []
        for note in split_review_notes(question.review_note):
            if is_analysis_failure_note(note):
                continue
            if is_low_confidence_note(note) or is_same_number_fallback_note(note):
                match_noise_notes.append(note)
                continue
            actionable_notes.append(note)

        can_auto_approve = is_structurally_safe_for_auto_review(
            stem_text=question.stem_text,
            page_start=question.page_start,
            has_unique_question_no=(question.paper_id, question.question_no) not in duplicate_keys,
            answer_text=question.answer.answer_text if question.answer else None,
        ) and not actionable_notes

        question.review_note = join_review_notes(actionable_notes if can_auto_approve else [*actionable_notes, *match_noise_notes])
        if can_auto_approve and question.review_status == "PENDING":
            question.review_status = "APPROVED"
        if (
            can_auto_approve
            and question.answer is not None
            and (
                question.answer.match_confidence is None
                or float(question.answer.match_confidence) < MATCH_AUTO_APPROVE_CONFIDENCE
            )
        ):
            question.answer.match_confidence = MATCH_AUTO_APPROVE_CONFIDENCE
            self.db.add(question.answer)

        changed = (
            original_note != question.review_note
            or original_status != question.review_status
            or (
                question.answer is not None
                and (
                    original_confidence
                    != (
                        float(question.answer.match_confidence)
                        if question.answer.match_confidence is not None
                        else None
                    )
                )
            )
        )
        if changed:
            self.db.add(question)
        return changed

    @staticmethod
    def _build_folder_names(questions: list[Question]) -> dict[int, str]:
        folder_names: dict[int, str] = {}
        grouped: dict[str, list[Question]] = {}
        for question in questions:
            grouped.setdefault(question.question_no, []).append(question)
        for question_no, group in grouped.items():
            ordered = sorted(group, key=lambda item: item.id)
            for index, question in enumerate(ordered, start=1):
                base = question_no.zfill(3) if question_no.isdigit() else slugify(question_no, separator="_")
                suffix = f"_dup{index}" if len(ordered) > 1 else ""
                folder_names[question.id] = f"q_{base}{suffix}"
        return folder_names

    def _build_question_payload(self, question: Question) -> dict[str, object]:
        existing = self._load_json_if_exists(question.question_json_path)
        existing["candidate_id"] = existing.get("candidate_id") or f"manual-question-{question.id}"
        existing["question_no"] = question.question_no
        existing["merged_text"] = question.stem_text
        existing["review_reason"] = question.review_note
        existing["blocks"] = existing.get("blocks") or []
        existing["image_blocks"] = existing.get("image_blocks") or []
        existing["image_refs"] = existing.get("image_refs") or existing["image_blocks"]
        existing["has_sub_questions"] = "（1）" in question.stem_text or "(1)" in question.stem_text
        return existing

    def _build_answer_payload(self, answer: QuestionAnswer) -> dict[str, object]:
        existing = self._load_json_if_exists(answer.answer_json_path)
        existing["candidate_id"] = existing.get("candidate_id") or f"manual-answer-{answer.question_id}"
        existing["answer_question_no"] = existing.get("answer_question_no") or ""
        existing["merged_text"] = answer.answer_text
        existing["review_reason"] = None
        existing["blocks"] = existing.get("blocks") or []
        existing["image_blocks"] = existing.get("image_blocks") or []
        existing["llm_text"] = answer.answer_text
        return existing

    def _delete_answer_record(self, answer: QuestionAnswer) -> None:
        for path in [answer.answer_md_path, answer.answer_json_path]:
            if path and self.storage.exists(path):
                self.storage.delete_file(path)
        self.db.delete(answer)

    @staticmethod
    def _collect_question_paths(question: Question) -> list[str]:
        paths = [question.question_md_path, question.question_json_path]
        if question.answer is not None:
            paths.extend([question.answer.answer_md_path, question.answer.answer_json_path])
        return [path for path in paths if path]

    def _load_json_if_exists(self, path: str | None) -> dict[str, object]:
        if not path or not self.storage.exists(path):
            return {}
        try:
            return json.loads(self.storage.read_file(path).decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return {}

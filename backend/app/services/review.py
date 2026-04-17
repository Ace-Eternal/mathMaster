from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Paper, Question, ReviewRecord
from app.schemas.question import ReviewQueueItem, ReviewUpdateRequest


class ReviewService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def update_question(self, question_id: int, payload: ReviewUpdateRequest) -> Question:
        question = self.db.execute(
            select(Question).options(selectinload(Question.answer)).where(Question.id == question_id)
        ).scalar_one()
        before = {
            "question_no": question.question_no,
            "stem_text": question.stem_text,
            "answer_text": question.answer.answer_text if question.answer else None,
            "match_status": question.answer.match_status if question.answer else None,
            "review_status": question.review_status,
            "review_note": question.review_note,
        }
        if payload.question_no is not None:
            question.question_no = payload.question_no
        if payload.stem_text is not None:
            question.stem_text = payload.stem_text
        if payload.review_note is not None:
            question.review_note = payload.review_note
        question.review_status = payload.review_status

        if question.answer and payload.answer_text is not None:
            question.answer.answer_text = payload.answer_text
        if question.answer and payload.match_status is not None:
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
        self.db.commit()
        self.db.refresh(question)
        return question

    def review_queue(
        self,
        *,
        paper_id: int | None = None,
        review_status: str | None = "PENDING",
        has_answer: bool | None = None,
        include_deleted: bool = False,
    ) -> list[ReviewQueueItem]:
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

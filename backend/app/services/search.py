from __future__ import annotations

import re

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import Paper, Question, QuestionAnswer, QuestionKnowledge, QuestionMethod


class SearchService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def search_papers(self, keyword: str | None, year: int | None, region: str | None, grade_level: str | None, term: str | None):
        stmt = select(Paper).order_by(Paper.created_at.desc())
        if keyword:
            stmt = stmt.where(Paper.title.like(f"%{keyword}%"))
        if year:
            stmt = stmt.where(Paper.year == year)
        if region:
            stmt = stmt.where(Paper.region == region)
        if grade_level:
            stmt = stmt.where(Paper.grade_level == grade_level)
        if term:
            stmt = stmt.where(Paper.term == term)
        stmt = stmt.where(Paper.is_deleted.is_(False))
        papers = list(self.db.execute(stmt).scalars())
        items = [
            {
                "id": paper.id,
                "title": paper.title,
                "year": paper.year,
                "region": paper.region,
                "grade_level": paper.grade_level,
                "term": paper.term,
                "status": paper.status,
            }
            for paper in papers
        ]
        return {"total": len(items), "items": items}

    def search_questions(
        self,
        *,
        keyword: str | None,
        question_type: str | None,
        year: int | None,
        region: str | None = None,
        grade_level: str | None = None,
        term: str | None = None,
        review_status: str | None = None,
        has_answer: bool | None = None,
        knowledge_point_id: int | None = None,
        solution_method_id: int | None = None,
        sort_by: str = "updated_desc",
        page: int,
        page_size: int,
        keyword_match_mode: str = "any",
    ):
        stmt = (
            select(Question, Paper)
            .join(Paper)
            .options(selectinload(Question.answer))
            .where(Paper.is_deleted.is_(False))
        )
        keywords = self._split_keywords(keyword)
        if keywords:
            keyword_conditions = [Question.stem_text.like(f"%{item}%") for item in keywords]
            stmt = stmt.where(and_(*keyword_conditions) if keyword_match_mode == "all" else or_(*keyword_conditions))
        if question_type:
            stmt = stmt.where(Question.question_type == question_type)
        if year:
            stmt = stmt.where(Paper.year == year)
        if region:
            stmt = stmt.where(Paper.region == region)
        if grade_level:
            stmt = stmt.where(Paper.grade_level == grade_level)
        if term:
            stmt = stmt.where(Paper.term == term)
        if review_status:
            stmt = stmt.where(Question.review_status == review_status)
        if knowledge_point_id:
            stmt = stmt.join(QuestionKnowledge).where(QuestionKnowledge.knowledge_point_id == knowledge_point_id)
        if solution_method_id:
            stmt = stmt.join(QuestionMethod).where(QuestionMethod.solution_method_id == solution_method_id)
        if has_answer is True:
            stmt = stmt.join(QuestionAnswer, QuestionAnswer.question_id == Question.id).where(QuestionAnswer.answer_text.is_not(None))
        elif has_answer is False:
            stmt = stmt.outerjoin(QuestionAnswer, QuestionAnswer.question_id == Question.id).where(QuestionAnswer.id.is_(None))

        if sort_by == "question_no":
            stmt = stmt.order_by(Question.question_no.asc(), Question.updated_at.desc())
        elif sort_by == "review_first":
            stmt = stmt.order_by(Question.review_status.asc(), Question.updated_at.desc())
        else:
            stmt = stmt.order_by(Question.updated_at.desc())
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        rows = self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
        items = [
            {
                "id": question.id,
                "paper_id": paper.id,
                "paper_title": paper.title,
                "question_no": question.question_no,
                "question_type": question.question_type,
                "stem_text": question.stem_text,
                "review_status": question.review_status,
                "year": paper.year,
                "region": paper.region,
                "grade_level": paper.grade_level,
                "term": paper.term,
                "has_answer": bool(question.answer and question.answer.answer_text),
            }
            for question, paper in rows
        ]
        return {"total": total, "items": items}

    @staticmethod
    def _split_keywords(keyword: str | None) -> list[str]:
        if not keyword:
            return []
        parts = re.split(r"[\s,，、;；]+", keyword)
        keywords: list[str] = []
        seen: set[str] = set()
        for part in parts:
            item = part.strip()
            if not item or item in seen:
                continue
            seen.add(item)
            keywords.append(item)
        return keywords

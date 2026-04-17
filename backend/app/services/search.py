from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import Paper, Question, QuestionKnowledge, QuestionMethod


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
        items = list(self.db.execute(stmt).scalars())
        return {"total": len(items), "items": items}

    def search_questions(
        self,
        *,
        keyword: str | None,
        question_type: str | None,
        year: int | None,
        knowledge_point_id: int | None,
        solution_method_id: int | None,
        page: int,
        page_size: int,
    ):
        stmt = select(Question).join(Paper).options(selectinload(Question.answer)).order_by(Question.created_at.desc())
        if keyword:
            stmt = stmt.where(Question.stem_text.like(f"%{keyword}%"))
        if question_type:
            stmt = stmt.where(Question.question_type == question_type)
        if year:
            stmt = stmt.where(Paper.year == year)
        if knowledge_point_id:
            stmt = stmt.join(QuestionKnowledge).where(QuestionKnowledge.knowledge_point_id == knowledge_point_id)
        if solution_method_id:
            stmt = stmt.join(QuestionMethod).where(QuestionMethod.solution_method_id == solution_method_id)
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        items = list(self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars())
        return {"total": total, "items": items}

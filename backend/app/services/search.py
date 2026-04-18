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
        knowledge_point_id: int | None,
        solution_method_id: int | None,
        page: int,
        page_size: int,
    ):
        stmt = (
            select(Question, Paper)
            .join(Paper)
            .options(selectinload(Question.answer))
            .where(Paper.is_deleted.is_(False))
            .order_by(Question.created_at.desc())
        )
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
            }
            for question, paper in rows
        ]
        return {"total": total, "items": items}

from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models import AppUser, Paper, Question, QuestionAnswer, QuestionKnowledge, QuestionMethod, UserQuestionState
from app.schemas.practice import PracticeStateResponse, PracticeSummaryItem, PracticeSummaryResponse


VALID_PRACTICE_STATUSES = {"NOT_STARTED", "IN_PROGRESS", "SOLVED"}


class PracticeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def random_question(
        self,
        *,
        user: AppUser,
        grade_levels: list[str] | None = None,
        knowledge_point_ids: list[int] | None = None,
        solution_method_ids: list[int] | None = None,
        question_type: str | None = None,
        year: int | None = None,
        region: str | None = None,
        term: str | None = None,
        has_answer: bool | None = None,
    ) -> tuple[Question, PracticeStateResponse, int]:
        stmt = self._filtered_question_stmt(
            grade_levels=grade_levels,
            knowledge_point_ids=knowledge_point_ids,
            solution_method_ids=solution_method_ids,
            question_type=question_type,
            year=year,
            region=region,
            term=term,
            has_answer=has_answer,
        )
        total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
        if total == 0:
            raise HTTPException(status_code=404, detail="No question matched current practice filters")
        question = self.db.execute(
            stmt.options(
                selectinload(Question.answer),
                selectinload(Question.analysis),
                selectinload(Question.knowledges).selectinload(QuestionKnowledge.knowledge_point),
                selectinload(Question.methods).selectinload(QuestionMethod.solution_method),
                selectinload(Question.paper).selectinload(Paper.answer_sheet),
            )
            .order_by(func.random())
            .limit(1)
        ).scalar_one()
        return question, self.get_state(user=user, question_id=question.id), total

    def update_state(
        self,
        *,
        user: AppUser,
        question_id: int,
        practice_status: str | None = None,
        is_favorited: bool | None = None,
    ) -> PracticeStateResponse:
        if practice_status is not None and practice_status not in VALID_PRACTICE_STATUSES:
            raise HTTPException(status_code=422, detail="Invalid practice status")
        question = self.db.get(Question, question_id)
        if question is None:
            raise HTTPException(status_code=404, detail="Question not found")
        state = self._get_or_create_state(user_id=user.id, question_id=question_id)
        now = datetime.utcnow()
        if practice_status is not None:
            state.practice_status = practice_status
            state.last_practiced_at = now
            state.solved_at = now if practice_status == "SOLVED" else None
        if is_favorited is not None:
            state.is_favorited = is_favorited
        self.db.add(state)
        self.db.commit()
        self.db.refresh(state)
        return self._state_response(state)

    def get_state(self, *, user: AppUser, question_id: int) -> PracticeStateResponse:
        state = self.db.execute(
            select(UserQuestionState).where(
                UserQuestionState.user_id == user.id,
                UserQuestionState.question_id == question_id,
            )
        ).scalar_one_or_none()
        if state is None:
            return PracticeStateResponse(question_id=question_id)
        return self._state_response(state)

    def summary(self, *, user: AppUser) -> PracticeSummaryResponse:
        in_progress_count = self._count_states(user.id, practice_status="IN_PROGRESS")
        solved_count = self._count_states(user.id, practice_status="SOLVED")
        favorite_count = self._count_states(user.id, is_favorited=True)
        return PracticeSummaryResponse(
            in_progress_count=in_progress_count,
            solved_count=solved_count,
            favorite_count=favorite_count,
            recent_in_progress=self._summary_items(user.id, practice_status="IN_PROGRESS"),
            recent_favorites=self._summary_items(user.id, is_favorited=True),
        )

    def _filtered_question_stmt(
        self,
        *,
        grade_levels: list[str] | None,
        knowledge_point_ids: list[int] | None,
        solution_method_ids: list[int] | None,
        question_type: str | None,
        year: int | None,
        region: str | None,
        term: str | None,
        has_answer: bool | None,
    ):
        stmt = select(Question).join(Paper).where(Paper.is_deleted.is_(False))
        if grade_levels:
            stmt = stmt.where(Paper.grade_level.in_([item for item in grade_levels if item]))
        if question_type:
            stmt = stmt.where(Question.question_type == question_type)
        if year:
            stmt = stmt.where(Paper.year == year)
        if region:
            stmt = stmt.where(Paper.region == region)
        if term:
            stmt = stmt.where(Paper.term == term)
        if knowledge_point_ids:
            stmt = stmt.join(QuestionKnowledge).where(QuestionKnowledge.knowledge_point_id.in_(knowledge_point_ids))
        if solution_method_ids:
            stmt = stmt.join(QuestionMethod).where(QuestionMethod.solution_method_id.in_(solution_method_ids))
        if has_answer is True:
            stmt = stmt.join(QuestionAnswer, QuestionAnswer.question_id == Question.id).where(QuestionAnswer.answer_text.is_not(None))
        elif has_answer is False:
            stmt = stmt.outerjoin(QuestionAnswer, QuestionAnswer.question_id == Question.id).where(QuestionAnswer.id.is_(None))
        return stmt.distinct()

    def _get_or_create_state(self, *, user_id: int, question_id: int) -> UserQuestionState:
        state = self.db.execute(
            select(UserQuestionState).where(
                UserQuestionState.user_id == user_id,
                UserQuestionState.question_id == question_id,
            )
        ).scalar_one_or_none()
        if state is None:
            state = UserQuestionState(user_id=user_id, question_id=question_id, practice_status="NOT_STARTED")
            self.db.add(state)
            self.db.flush()
        return state

    def _count_states(self, user_id: int, *, practice_status: str | None = None, is_favorited: bool | None = None) -> int:
        stmt = select(func.count(UserQuestionState.id)).where(UserQuestionState.user_id == user_id)
        if practice_status:
            stmt = stmt.where(UserQuestionState.practice_status == practice_status)
        if is_favorited is not None:
            stmt = stmt.where(UserQuestionState.is_favorited.is_(is_favorited))
        return self.db.execute(stmt).scalar_one()

    def _summary_items(
        self,
        user_id: int,
        *,
        practice_status: str | None = None,
        is_favorited: bool | None = None,
        limit: int = 5,
    ) -> list[PracticeSummaryItem]:
        stmt = (
            select(UserQuestionState, Question, Paper)
            .join(Question, Question.id == UserQuestionState.question_id)
            .join(Paper, Paper.id == Question.paper_id)
            .where(UserQuestionState.user_id == user_id, Paper.is_deleted.is_(False))
        )
        if practice_status:
            stmt = stmt.where(UserQuestionState.practice_status == practice_status)
        if is_favorited is not None:
            stmt = stmt.where(UserQuestionState.is_favorited.is_(is_favorited))
        rows = self.db.execute(stmt.order_by(UserQuestionState.updated_at.desc()).limit(limit)).all()
        return [
            PracticeSummaryItem(
                question_id=question.id,
                paper_id=paper.id,
                paper_title=paper.title,
                question_no=question.question_no,
                stem_text=question.stem_text,
                practice_status=state.practice_status,
                is_favorited=state.is_favorited,
                last_practiced_at=state.last_practiced_at,
                solved_at=state.solved_at,
            )
            for state, question, paper in rows
        ]

    @staticmethod
    def _state_response(state: UserQuestionState) -> PracticeStateResponse:
        return PracticeStateResponse(
            question_id=state.question_id,
            practice_status=state.practice_status,
            is_favorited=state.is_favorited,
            last_practiced_at=state.last_practiced_at,
            solved_at=state.solved_at,
        )

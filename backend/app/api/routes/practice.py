from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.routes.questions import _build_question_detail_response_payload, get_question
from app.db.session import get_db
from app.models import AppUser
from app.schemas.practice import (
    PracticeQuestionResponse,
    PracticeStateResponse,
    PracticeStateUpdateRequest,
    PracticeSummaryResponse,
)
from app.services.audit import write_audit_log
from app.services.auth import request_meta, require_permission
from app.services.practice import PracticeService

router = APIRouter()


def _split_csv(values: list[str] | None) -> list[str]:
    items: list[str] = []
    for value in values or []:
        items.extend(part.strip() for part in str(value).split(",") if part.strip())
    return list(dict.fromkeys(items))


@router.get("/random-question", response_model=PracticeQuestionResponse)
def random_question(
    request: Request,
    grade_levels: list[str] | None = Query(default=None),
    knowledge_point_ids: list[int] | None = Query(default=None),
    solution_method_ids: list[int] | None = Query(default=None),
    question_type: str | None = None,
    year: int | None = None,
    region: str | None = None,
    term: str | None = None,
    has_answer: bool | None = None,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("practice.use")),
):
    question, state, total = PracticeService(db).random_question(
        user=user,
        grade_levels=_split_csv(grade_levels),
        knowledge_point_ids=knowledge_point_ids,
        solution_method_ids=solution_method_ids,
        question_type=question_type,
        year=year,
        region=region,
        term=term,
        has_answer=has_answer,
    )
    detail = get_question(question.id, request, db)
    return PracticeQuestionResponse(question=detail, practice_state=state, match_count=total)


@router.patch("/questions/{question_id}/state", response_model=PracticeStateResponse)
def update_question_state(
    question_id: int,
    payload: PracticeStateUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("practice.use")),
):
    before = PracticeService(db).get_state(user=user, question_id=question_id)
    state = PracticeService(db).update_state(
        user=user,
        question_id=question_id,
        practice_status=payload.practice_status,
        is_favorited=payload.is_favorited,
    )
    write_audit_log(
        db,
        actor=user,
        action="practice.update_state",
        resource_type="question",
        resource_id=question_id,
        before=before.model_dump(),
        after=state.model_dump(),
        **request_meta(request),
    )
    db.commit()
    return state


@router.get("/summary", response_model=PracticeSummaryResponse)
def practice_summary(
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("practice.use")),
):
    return PracticeService(db).summary(user=user)

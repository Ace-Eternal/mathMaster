from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import QuestionDetailResponse, ReviewQueueItem, ReviewUpdateRequest
from app.services.review import ReviewService

router = APIRouter()


@router.post("/questions/{question_id}", response_model=QuestionDetailResponse)
def review_question(question_id: int, payload: ReviewUpdateRequest, db: Session = Depends(get_db)):
    question = ReviewService(db).update_question(question_id, payload)
    return QuestionDetailResponse.model_validate(question)


@router.get("/queue", response_model=list[ReviewQueueItem])
def review_queue(
    paper_id: int | None = None,
    review_status: str = Query(default="PENDING"),
    has_answer: bool | None = None,
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return ReviewService(db).review_queue(
        paper_id=paper_id,
        review_status=review_status,
        has_answer=has_answer,
        include_deleted=include_deleted,
    )

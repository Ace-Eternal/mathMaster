from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import QuestionDetailResponse, ReviewQueueItem, ReviewUpdateRequest
from app.services.review import ReviewService
from app.services.storage.factory import get_storage_service

router = APIRouter()


@router.post("/questions/{question_id}", response_model=QuestionDetailResponse)
def review_question(question_id: int, payload: ReviewUpdateRequest, db: Session = Depends(get_db)):
    service = ReviewService(db, get_storage_service())
    question = service.update_question(question_id, payload)
    return service.build_question_detail_response(question.id)


@router.get("/queue", response_model=list[ReviewQueueItem])
def review_queue(
    paper_id: int | None = None,
    review_status: str = Query(default="PENDING"),
    has_answer: bool | None = None,
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return ReviewService(db, get_storage_service()).review_queue(
        paper_id=paper_id,
        review_status=review_status,
        has_answer=has_answer,
        include_deleted=include_deleted,
    )

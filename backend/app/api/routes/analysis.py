from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AppUser
from app.schemas.question import AnalysisRunResponse
from app.schemas.paper import PipelineTaskResponse
from app.services.pipeline_queue import pipeline_task_queue
from app.services.auth import require_permission

router = APIRouter()


def build_task_response(task) -> PipelineTaskResponse:
    return PipelineTaskResponse(
        id=task.id,
        paper_id=task.paper_id,
        question_id=task.question_id,
        task_type=task.task_type,
        status=task.status,
        source=task.source,
        depends_on_task_id=task.depends_on_task_id,
        queued_at=task.queued_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
        error_message=task.error_message,
        blocked_reason=task.blocked_reason,
        attempt_count=task.attempt_count,
        max_attempts=task.max_attempts,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.post("/questions/{question_id}", response_model=AnalysisRunResponse)
def analyze_question(question_id: int, db: Session = Depends(get_db), user: AppUser = Depends(require_permission("question.edit"))):
    task = pipeline_task_queue.enqueue_analysis(db, question_id=question_id, source="SINGLE")
    db.commit()
    db.refresh(task)
    pipeline_task_queue.notify()
    return AnalysisRunResponse(
        question_id=question_id,
        pipeline_task=build_task_response(task),
    )

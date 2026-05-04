from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.paper import PipelineTaskResponse
from app.services.pipeline_queue import pipeline_task_queue

router = APIRouter()


def build_task_response(task, *, queue_position: int | None = None) -> PipelineTaskResponse:
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
        queue_position=queue_position,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


@router.get("", response_model=list[PipelineTaskResponse])
def list_tasks(
    paper_id: int | None = None,
    question_id: int | None = None,
    task_type: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    tasks = pipeline_task_queue.list_visible_tasks(
        db,
        paper_id=paper_id,
        question_id=question_id,
        task_type=task_type,
        status=status,
    )
    queued_position = 0
    responses: list[PipelineTaskResponse] = []
    for task in tasks:
        position = None
        if task.status == "QUEUED":
            queued_position += 1
            position = queued_position
        responses.append(build_task_response(task, queue_position=position))
    return responses

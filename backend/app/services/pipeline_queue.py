from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Paper, PipelineTask
from app.services.llm.gateway import LLMGateway
from app.services.mineu.service import MineuService
from app.services.pipeline import MatchService, PaperPipelineService, SliceService
from app.services.storage.factory import get_storage_service


ACTIVE_TASK_STATUSES = {"QUEUED", "RUNNING"}
VISIBLE_TASK_STATUSES = {"QUEUED", "RUNNING", "FAILED"}
logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _build_pipeline_service(db: Session) -> PaperPipelineService:
    return PaperPipelineService(
        db=db,
        storage=get_storage_service(),
        mineu_service=MineuService(),
        slice_service=SliceService(),
        match_service=MatchService(LLMGateway()),
    )


class PipelineTaskQueue:
    def __init__(self) -> None:
        self._wake_event = threading.Event()
        self._worker: threading.Thread | None = None
        self._lock = threading.Lock()
        self._stop_requested = False

    def start(self) -> None:
        with self._lock:
            if self._worker and self._worker.is_alive():
                return
            self._stop_requested = False
            self.requeue_running_tasks()
            self._worker = threading.Thread(target=self._worker_loop, name="pipeline-task-worker", daemon=True)
            self._worker.start()
            self._wake_event.set()

    def stop(self) -> None:
        self._stop_requested = True
        self._wake_event.set()

    def notify(self) -> None:
        self._wake_event.set()

    def enqueue(self, db: Session, *, paper_id: int, source: str) -> PipelineTask:
        paper = db.get(Paper, paper_id)
        if not paper or paper.is_deleted:
            raise HTTPException(status_code=404, detail="Paper not found")

        existing = db.execute(
            select(PipelineTask)
            .where(PipelineTask.paper_id == paper_id, PipelineTask.status.in_(ACTIVE_TASK_STATUSES))
            .order_by(PipelineTask.queued_at.asc(), PipelineTask.id.asc())
        ).scalars().first()
        if existing:
            return existing

        task = PipelineTask(
            paper_id=paper_id,
            status="QUEUED",
            source=source,
            queued_at=utc_now(),
        )
        db.add(task)
        db.flush()
        self.notify()
        return task

    def list_visible_tasks(self, db: Session) -> list[PipelineTask]:
        return list(
            db.execute(
                select(PipelineTask)
                .where(PipelineTask.status.in_(VISIBLE_TASK_STATUSES))
                .order_by(PipelineTask.queued_at.asc(), PipelineTask.id.asc())
            ).scalars()
        )

    def requeue_running_tasks(self) -> int:
        with SessionLocal() as db:
            running_tasks = list(db.execute(select(PipelineTask).where(PipelineTask.status == "RUNNING")).scalars())
            for task in running_tasks:
                task.status = "QUEUED"
                task.started_at = None
                task.error_message = None
                db.add(task)
            if running_tasks:
                db.commit()
            return len(running_tasks)

    def _worker_loop(self) -> None:
        while not self._stop_requested:
            task_payload = self._claim_next_task()
            if task_payload is None:
                self._wake_event.wait(timeout=5)
                self._wake_event.clear()
                continue

            task_id, paper_id = task_payload
            try:
                with SessionLocal() as db:
                    _build_pipeline_service(db).run_pipeline(paper_id)
                self._mark_task_success(task_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Pipeline task %s failed for paper %s", task_id, paper_id)
                self._mark_task_failed(task_id, str(exc))

    def _claim_next_task(self) -> tuple[int, int] | None:
        with SessionLocal() as db:
            task = db.execute(
                select(PipelineTask)
                .where(PipelineTask.status == "QUEUED")
                .order_by(PipelineTask.queued_at.asc(), PipelineTask.id.asc())
            ).scalars().first()
            if task is None:
                return None
            task.status = "RUNNING"
            task.started_at = utc_now()
            task.finished_at = None
            task.error_message = None
            db.add(task)
            db.commit()
            return task.id, task.paper_id

    def _mark_task_success(self, task_id: int) -> None:
        with SessionLocal() as db:
            task = db.get(PipelineTask, task_id)
            if not task:
                return
            task.status = "SUCCESS"
            task.finished_at = utc_now()
            task.error_message = None
            db.add(task)
            db.commit()

    def _mark_task_failed(self, task_id: int, error_message: str) -> None:
        with SessionLocal() as db:
            task = db.get(PipelineTask, task_id)
            if not task:
                return
            task.status = "FAILED"
            task.finished_at = utc_now()
            task.error_message = error_message[:4000]
            db.add(task)
            db.commit()


pipeline_task_queue = PipelineTaskQueue()

from __future__ import annotations

import logging
import threading
from collections.abc import Iterable
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Paper, PipelineTask, Question
from app.services.analysis import KnowledgeAnalysisService
from app.services.llm.gateway import LLMGateway
from app.services.mineu.service import MineuService
from app.services.pipeline import MatchService, PaperPipelineService, SliceService
from app.services.storage.factory import get_storage_service


TASK_TYPE_MINEU_CONVERT = "MINEU_CONVERT"
TASK_TYPE_SLICE_MATCH = "SLICE_MATCH"
TASK_TYPE_QUESTION_ANALYSIS = "QUESTION_ANALYSIS"
ACTIVE_TASK_STATUSES = {"QUEUED", "RUNNING", "BLOCKED"}
VISIBLE_TASK_STATUSES = {"QUEUED", "RUNNING", "BLOCKED", "FAILED"}
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
    def __init__(self, *, mineu_workers: int = 2, slice_workers: int = 1, analysis_workers: int = 2) -> None:
        self._wake_event = threading.Event()
        self._workers: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._stop_requested = False
        self._lanes: list[tuple[str, tuple[str, ...], int]] = [
            ("mineu", (TASK_TYPE_MINEU_CONVERT,), mineu_workers),
            ("slice", (TASK_TYPE_SLICE_MATCH,), slice_workers),
            ("analysis", (TASK_TYPE_QUESTION_ANALYSIS,), analysis_workers),
        ]

    def start(self) -> None:
        with self._lock:
            if any(worker.is_alive() for worker in self._workers):
                return
            self._stop_requested = False
            self.requeue_running_tasks()
            self._release_ready_blocked_tasks()
            self._workers = []
            for lane_name, task_types, worker_count in self._lanes:
                for worker_index in range(worker_count):
                    worker = threading.Thread(
                        target=self._worker_loop,
                        args=(task_types,),
                        name=f"pipeline-task-worker-{lane_name}-{worker_index + 1}",
                        daemon=True,
                    )
                    worker.start()
                    self._workers.append(worker)
            self._wake_event.set()

    def stop(self) -> None:
        self._stop_requested = True
        self._wake_event.set()

    def notify(self) -> None:
        self._wake_event.set()

    def enqueue(self, db: Session, *, paper_id: int, source: str) -> PipelineTask:
        mineu_task, _ = self.enqueue_pipeline(db, paper_id=paper_id, source=source)
        return mineu_task

    def enqueue_pipeline(self, db: Session, *, paper_id: int, source: str) -> tuple[PipelineTask, PipelineTask]:
        paper = db.get(Paper, paper_id)
        if not paper or paper.is_deleted:
            raise HTTPException(status_code=404, detail="Paper not found")

        mineu_task = self._get_or_create_paper_task(
            db,
            paper_id=paper.id,
            task_type=TASK_TYPE_MINEU_CONVERT,
            source=source,
            status="QUEUED",
            blocked_reason=None,
        )
        slice_status = "QUEUED" if mineu_task.status == "SUCCESS" else "BLOCKED"
        slice_task = self._get_or_create_paper_task(
            db,
            paper_id=paper.id,
            task_type=TASK_TYPE_SLICE_MATCH,
            source=source,
            status=slice_status,
            depends_on_task_id=mineu_task.id,
            blocked_reason=None if slice_status == "QUEUED" else "等待 MineU 转换完成",
        )
        self.notify()
        return mineu_task, slice_task

    def enqueue_analysis(self, db: Session, *, question_id: int, source: str = "SINGLE") -> PipelineTask:
        question = db.get(Question, question_id)
        if question is None:
            raise HTTPException(status_code=404, detail="Question not found")
        existing = db.execute(
            select(PipelineTask)
            .where(
                PipelineTask.question_id == question_id,
                PipelineTask.task_type == TASK_TYPE_QUESTION_ANALYSIS,
                PipelineTask.status.in_(ACTIVE_TASK_STATUSES),
            )
            .order_by(PipelineTask.queued_at.asc(), PipelineTask.id.asc())
        ).scalars().first()
        if existing:
            return existing

        task = PipelineTask(
            paper_id=question.paper_id,
            question_id=question.id,
            task_type=TASK_TYPE_QUESTION_ANALYSIS,
            status="QUEUED",
            source=source,
            queued_at=utc_now(),
        )
        db.add(task)
        db.flush()
        self.notify()
        return task

    def list_visible_tasks(
        self,
        db: Session,
        *,
        paper_id: int | None = None,
        question_id: int | None = None,
        task_type: str | None = None,
        status: str | None = None,
    ) -> list[PipelineTask]:
        stmt = select(PipelineTask).where(PipelineTask.status.in_(VISIBLE_TASK_STATUSES))
        if paper_id is not None:
            stmt = stmt.where(PipelineTask.paper_id == paper_id)
        if question_id is not None:
            stmt = stmt.where(PipelineTask.question_id == question_id)
        if task_type:
            stmt = stmt.where(PipelineTask.task_type == task_type)
        if status:
            stmt = stmt.where(PipelineTask.status == status)
        return list(db.execute(stmt.order_by(PipelineTask.queued_at.asc(), PipelineTask.id.asc())).scalars())

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

    def _get_or_create_paper_task(
        self,
        db: Session,
        *,
        paper_id: int,
        task_type: str,
        source: str,
        status: str,
        depends_on_task_id: int | None = None,
        blocked_reason: str | None = None,
    ) -> PipelineTask:
        existing = db.execute(
            select(PipelineTask)
            .where(
                PipelineTask.paper_id == paper_id,
                PipelineTask.task_type == task_type,
                PipelineTask.status.in_(ACTIVE_TASK_STATUSES),
            )
            .order_by(PipelineTask.queued_at.asc(), PipelineTask.id.asc())
        ).scalars().first()
        if existing:
            return existing
        task = PipelineTask(
            paper_id=paper_id,
            task_type=task_type,
            status=status,
            source=source,
            depends_on_task_id=depends_on_task_id,
            blocked_reason=blocked_reason,
            queued_at=utc_now(),
        )
        db.add(task)
        db.flush()
        return task

    def _worker_loop(self, task_types: Iterable[str]) -> None:
        lane_task_types = tuple(task_types)
        while not self._stop_requested:
            task_payload = self._claim_next_task(lane_task_types)
            if task_payload is None:
                self._wake_event.wait(timeout=5)
                self._wake_event.clear()
                continue

            task_id, task_type, paper_id, question_id = task_payload
            try:
                self._execute_task(task_type=task_type, paper_id=paper_id, question_id=question_id)
                self._mark_task_success(task_id)
                self._release_dependents(task_id)
            except Exception as exc:  # noqa: BLE001
                logger.exception("Pipeline task %s failed", task_id)
                self._mark_task_failed(task_id, str(exc))
                self._block_dependents(task_id, str(exc))

    def _execute_task(self, *, task_type: str, paper_id: int | None, question_id: int | None) -> None:
        with SessionLocal() as db:
            if task_type == TASK_TYPE_MINEU_CONVERT:
                if paper_id is None:
                    raise ValueError("MineU task missing paper_id")
                _build_pipeline_service(db).run_mineu_conversion(paper_id)
                return
            if task_type == TASK_TYPE_SLICE_MATCH:
                if paper_id is None:
                    raise ValueError("Slice/match task missing paper_id")
                question_ids = _build_pipeline_service(db).run_slice_match(paper_id)
                for created_question_id in question_ids:
                    self.enqueue_analysis(db, question_id=created_question_id, source="PIPELINE")
                db.commit()
                return
            if task_type == TASK_TYPE_QUESTION_ANALYSIS:
                if question_id is None:
                    raise ValueError("Analysis task missing question_id")
                KnowledgeAnalysisService(db, LLMGateway()).analyze_question(question_id)
                return
            raise ValueError(f"Unsupported task type: {task_type}")

    def _claim_next_task(self, task_types: Iterable[str] | None = None) -> tuple[int, str, int | None, int | None] | None:
        with SessionLocal() as db:
            stmt = select(PipelineTask).where(PipelineTask.status == "QUEUED")
            if task_types is not None:
                stmt = stmt.where(PipelineTask.task_type.in_(tuple(task_types)))
            task = db.execute(stmt.order_by(PipelineTask.queued_at.asc(), PipelineTask.id.asc())).scalars().first()
            if task is None:
                return None
            task.status = "RUNNING"
            task.started_at = utc_now()
            task.finished_at = None
            task.error_message = None
            task.blocked_reason = None
            task.attempt_count = (task.attempt_count or 0) + 1
            db.add(task)
            db.commit()
            return task.id, task.task_type, task.paper_id, task.question_id

    def _mark_task_success(self, task_id: int) -> None:
        with SessionLocal() as db:
            task = db.get(PipelineTask, task_id)
            if not task:
                return
            task.status = "SUCCESS"
            task.finished_at = utc_now()
            task.error_message = None
            task.blocked_reason = None
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
            task.blocked_reason = None
            db.add(task)
            db.commit()

    def _release_dependents(self, task_id: int) -> None:
        with SessionLocal() as db:
            dependents = list(
                db.execute(
                    select(PipelineTask).where(
                        PipelineTask.depends_on_task_id == task_id,
                        PipelineTask.status == "BLOCKED",
                    )
                ).scalars()
            )
            for task in dependents:
                task.status = "QUEUED"
                task.blocked_reason = None
                db.add(task)
            if dependents:
                db.commit()
                self.notify()

    def _block_dependents(self, task_id: int, error_message: str) -> None:
        with SessionLocal() as db:
            dependents = list(
                db.execute(
                    select(PipelineTask).where(
                        PipelineTask.depends_on_task_id == task_id,
                        PipelineTask.status.in_({"QUEUED", "BLOCKED"}),
                    )
                ).scalars()
            )
            for task in dependents:
                task.status = "BLOCKED"
                task.blocked_reason = f"依赖任务失败: {error_message}"[:4000]
                db.add(task)
            if dependents:
                db.commit()

    def _release_ready_blocked_tasks(self) -> None:
        with SessionLocal() as db:
            blocked_tasks = list(
                db.execute(
                    select(PipelineTask).where(
                        PipelineTask.status == "BLOCKED",
                        PipelineTask.depends_on_task_id.is_not(None),
                    )
                ).scalars()
            )
            changed = False
            for task in blocked_tasks:
                dependency = db.get(PipelineTask, task.depends_on_task_id)
                if dependency and dependency.status == "SUCCESS":
                    task.status = "QUEUED"
                    task.blocked_reason = None
                    db.add(task)
                    changed = True
            if changed:
                db.commit()


pipeline_task_queue = PipelineTaskQueue()

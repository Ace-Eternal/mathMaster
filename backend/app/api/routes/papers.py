from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.paper import (
    BatchRunRequest,
    ImportFoldersResponse,
    ImportJobResponse,
    MineuPreviewResponse,
    PaperResponse,
    PaperUpdateRequest,
    PipelineRunResponse,
)
from app.schemas.question import QuestionCreateRequest, QuestionUpdateRequest
from app.services.llm.gateway import LLMGateway
from app.services.mineu.service import MineuService
from app.services.pipeline import MatchService, PaperPipelineService, SliceService
from app.services.review import ReviewService
from app.services.storage.factory import get_storage_service

router = APIRouter()


def get_pipeline_service(db: Session) -> PaperPipelineService:
    return PaperPipelineService(
        db=db,
        storage=get_storage_service(),
        mineu_service=MineuService(),
        slice_service=SliceService(),
        match_service=MatchService(LLMGateway()),
    )


@router.get("", response_model=list[PaperResponse])
def list_papers(db: Session = Depends(get_db)):
    return get_pipeline_service(db).list_papers()


@router.get("/manage", response_model=list[PaperResponse])
def manage_papers(
    keyword: str | None = None,
    year: int | None = None,
    region: str | None = None,
    grade_level: str | None = None,
    term: str | None = None,
    status: str | None = None,
    has_answer: bool | None = None,
    include_deleted: bool = Query(default=False),
    db: Session = Depends(get_db),
):
    return get_pipeline_service(db).list_manage_papers(
        keyword=keyword,
        year=year,
        region=region,
        grade_level=grade_level,
        term=term,
        status=status,
        has_answer=has_answer,
        include_deleted=include_deleted,
    )


@router.post("/upload", response_model=PaperResponse)
async def upload_paper(
    paper_file: UploadFile = File(...),
    answer_file: UploadFile | None = File(default=None),
    title: str | None = Form(default=None),
    source: str | None = Form(default=None),
    region: str | None = Form(default=None),
    grade_level: str | None = Form(default=None),
    term: str | None = Form(default=None),
    subject: str = Form(default="math"),
    db: Session = Depends(get_db),
):
    service = get_pipeline_service(db)
    return await service.ingest_uploads(
        paper_file=paper_file,
        answer_file=answer_file,
        title=title,
        source=source,
        region=region,
        grade_level=grade_level,
        term=term,
        subject=subject,
    )


@router.post("/import-folders", response_model=ImportFoldersResponse)
async def import_folders(
    paper_files: list[UploadFile] = File(...),
    answer_files: list[UploadFile] = File(default=[]),
    subject: str = Form(default="math"),
    db: Session = Depends(get_db),
):
    service = get_pipeline_service(db)
    import_job, items = await service.import_folder_uploads(
        paper_files=paper_files,
        answer_files=answer_files,
        subject=subject,
    )
    return ImportFoldersResponse(
        import_job=ImportJobResponse(
            id=import_job.id,
            status=import_job.status,
            summary=json.loads(import_job.summary_json),
            created_at=import_job.created_at,
            updated_at=import_job.updated_at,
        ),
        items=items,
    )


@router.get("/import-jobs/{import_job_id}", response_model=ImportJobResponse)
def get_import_job(import_job_id: int, db: Session = Depends(get_db)):
    import_job = get_pipeline_service(db).get_import_job(import_job_id)
    return ImportJobResponse(
        id=import_job.id,
        status=import_job.status,
        summary=json.loads(import_job.summary_json),
        created_at=import_job.created_at,
        updated_at=import_job.updated_at,
    )


@router.post("/batch/run", response_model=list[PipelineRunResponse])
def batch_run(payload: BatchRunRequest, db: Session = Depends(get_db)):
    papers = get_pipeline_service(db).batch_run_pipeline(payload.paper_ids)
    return [
        PipelineRunResponse(
            paper_id=paper.id,
            paper_status=paper.status,
            jobs=paper.conversion_jobs,
            question_count=len(paper.questions),
            questions=paper.questions,
        )
        for paper in papers
    ]


@router.patch("/{paper_id}", response_model=PaperResponse)
def update_paper(paper_id: int, payload: PaperUpdateRequest, db: Session = Depends(get_db)):
    return get_pipeline_service(db).update_paper(paper_id, payload.model_dump(exclude_unset=True))


@router.post("/{paper_id}/questions", response_model=PaperResponse)
def create_question(paper_id: int, payload: QuestionCreateRequest, db: Session = Depends(get_db)):
    service = ReviewService(db, get_storage_service())
    service.create_question(paper_id, payload)
    return get_pipeline_service(db).get_paper(paper_id)


@router.patch("/{paper_id}/questions/{question_id}", response_model=PaperResponse)
def patch_question(paper_id: int, question_id: int, payload: QuestionUpdateRequest, db: Session = Depends(get_db)):
    service = ReviewService(db, get_storage_service())
    service.patch_question(paper_id, question_id, payload)
    return get_pipeline_service(db).get_paper(paper_id)


@router.delete("/{paper_id}/questions/{question_id}", response_model=PaperResponse)
def delete_question(paper_id: int, question_id: int, db: Session = Depends(get_db)):
    service = ReviewService(db, get_storage_service())
    service.delete_question(paper_id, question_id)
    return get_pipeline_service(db).get_paper(paper_id)


@router.delete("/{paper_id}", response_model=PaperResponse)
def soft_delete_paper(paper_id: int, db: Session = Depends(get_db)):
    return get_pipeline_service(db).soft_delete_paper(paper_id)


@router.post("/{paper_id}/restore", response_model=PaperResponse)
def restore_paper(paper_id: int, db: Session = Depends(get_db)):
    return get_pipeline_service(db).restore_paper(paper_id)


@router.post("/{paper_id}/answer/bind", response_model=PaperResponse)
async def bind_answer(
    paper_id: int,
    answer_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return await get_pipeline_service(db).bind_answer_upload(paper_id, answer_file)


@router.post("/{paper_id}/answer/unbind", response_model=PaperResponse)
def unbind_answer(paper_id: int, db: Session = Depends(get_db)):
    return get_pipeline_service(db).unbind_answer(paper_id)


@router.post("/{paper_id}/pipeline/run", response_model=PipelineRunResponse)
@router.post("/{paper_id}/pipeline/run-all", response_model=PipelineRunResponse)
def run_pipeline(paper_id: int, db: Session = Depends(get_db)):
    paper = get_pipeline_service(db).run_pipeline(paper_id)
    return PipelineRunResponse(
        paper_id=paper.id,
        paper_status=paper.status,
        jobs=paper.conversion_jobs,
        question_count=len(paper.questions),
        questions=paper.questions,
    )


@router.get("/{paper_id}", response_model=PaperResponse)
def get_paper(paper_id: int, db: Session = Depends(get_db)):
    return get_pipeline_service(db).get_paper(paper_id)


@router.get("/{paper_id}/mineu-preview", response_model=MineuPreviewResponse)
def get_mineu_preview(paper_id: int, db: Session = Depends(get_db)):
    paper = get_pipeline_service(db).get_paper(paper_id)
    storage = get_storage_service()
    outputs = {}
    for job in paper.conversion_jobs:
        json_preview = json.loads(storage.read_file(job.json_path).decode("utf-8")) if job.json_path else None
        if isinstance(json_preview, list):
            preview_blocks = json_preview
        else:
            preview_blocks = (json_preview or {}).get("blocks", [])
        outputs[job.job_type.lower()] = {
            "markdown_path": job.markdown_path,
            "json_path": job.json_path,
            "raw_response_path": job.raw_response_path,
            "markdown_preview": storage.read_file(job.markdown_path).decode("utf-8") if job.markdown_path else None,
            "json_preview": json_preview,
            "image_blocks": [
                block
                for block in preview_blocks
                if "image" in str(block.get("type") or block.get("block_type") or "").lower() or block.get("image_url")
            ],
        }
    return MineuPreviewResponse(paper_id=paper.id, outputs=outputs)

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedResponse


class PaperCreateRequest(BaseModel):
    title: str
    year: int | None = None
    source: str | None = None
    grade_level: str | None = None
    region: str | None = None
    term: str | None = None


class PaperUpdateRequest(BaseModel):
    title: str | None = None
    year: int | None = None
    source: str | None = None
    grade_level: str | None = None
    region: str | None = None
    term: str | None = None
    status: str | None = None
    has_answer: bool | None = None


class ConversionJobResponse(TimestampedResponse):
    id: int
    job_type: str
    provider: str
    status: str
    markdown_path: str | None = None
    json_path: str | None = None
    raw_response_path: str | None = None
    error_message: str | None = None
    version_no: int


class AnswerSheetResponse(TimestampedResponse):
    id: int
    paper_id: int
    answer_pdf_path: str | None = None
    answer_pdf_hash: str | None = None
    has_answer: bool
    status: str


class QuestionSummary(ORMModel):
    id: int
    question_no: str
    question_type: str | None = None
    stem_text: str
    review_status: str
    review_note: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class PaperResponse(TimestampedResponse):
    id: int
    title: str
    year: int | None = None
    source: str | None = None
    grade_level: str | None = None
    region: str | None = None
    term: str | None = None
    paper_pdf_path: str
    paper_pdf_hash: str
    status: str
    is_deleted: bool = False
    deleted_at: datetime | None = None
    latest_error_message: str | None = None
    last_pipeline_at: datetime | None = None
    answer_sheet: AnswerSheetResponse | None = None
    conversion_jobs: list[ConversionJobResponse] = Field(default_factory=list)
    questions: list[QuestionSummary] = Field(default_factory=list)
    pending_review_count: int = 0


class PipelineTaskResponse(TimestampedResponse):
    id: int
    paper_id: int
    status: str
    source: str
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    queue_position: int | None = None


class PipelineRunResponse(BaseModel):
    paper_id: int
    paper_status: str
    jobs: list[ConversionJobResponse]
    question_count: int
    questions: list[QuestionSummary]
    pipeline_task: PipelineTaskResponse | None = None


class MineuPreviewResponse(BaseModel):
    paper_id: int
    outputs: dict[str, Any]


class ImportPairItem(BaseModel):
    paper_filename: str
    answer_filename: str | None = None
    pair_key: str
    paper_id: int | None = None
    pair_status: str
    has_answer: bool


class ImportJobResponse(TimestampedResponse):
    id: int
    status: str
    summary: dict[str, Any]


class ImportFoldersResponse(BaseModel):
    import_job: ImportJobResponse
    items: list[ImportPairItem]


class BatchRunRequest(BaseModel):
    paper_ids: list[int]

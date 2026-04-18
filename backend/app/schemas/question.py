from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel, TimestampedResponse


class QuestionAnswerResponse(TimestampedResponse):
    id: int
    answer_text: str | None = None
    answer_md_path: str | None = None
    answer_json_path: str | None = None
    match_confidence: float | None = None
    match_status: str


class QuestionAnalysisResponse(TimestampedResponse):
    id: int
    analysis_json: str
    explanation_md: str | None = None
    model_name: str | None = None
    version_no: int
    review_status: str


class KnowledgeLite(ORMModel):
    id: int
    name: str
    level: int


class MethodLite(ORMModel):
    id: int
    name: str
    description: str | None = None


class QuestionDetailResponse(TimestampedResponse):
    id: int
    paper_id: int
    question_no: str
    question_type: str | None = None
    stem_text: str
    question_md_path: str | None = None
    question_json_path: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    review_status: str
    review_note: str | None = None
    answer: QuestionAnswerResponse | None = None
    analysis: QuestionAnalysisResponse | None = None
    knowledges: list[KnowledgeLite] = Field(default_factory=list)
    methods: list[MethodLite] = Field(default_factory=list)
    assets: dict[str, Any] = Field(default_factory=dict)


class ReviewUpdateRequest(BaseModel):
    question_no: str | None = None
    question_type: str | None = None
    stem_text: str | None = None
    answer_text: str | None = None
    match_status: str | None = None
    review_status: str = "FIXED"
    review_note: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    comment: str | None = None
    reviewer_id: str | None = None
    review_type: str = "MATCH_CORRECTION"


class QuestionCreateRequest(BaseModel):
    question_no: str
    question_type: str | None = None
    stem_text: str
    answer_text: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    review_status: str = "PENDING"
    review_note: str | None = None


class QuestionUpdateRequest(BaseModel):
    question_no: str | None = None
    question_type: str | None = None
    stem_text: str | None = None
    answer_text: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    review_status: str | None = None
    review_note: str | None = None


class ReviewQueueItem(ORMModel):
    question_id: int
    paper_id: int
    paper_title: str
    question_no: str
    stem_text: str
    review_status: str
    review_note: str | None = None
    match_confidence: float | None = None
    has_answer: bool


class AnalysisRunResponse(BaseModel):
    question_id: int
    analysis_id: int
    knowledges: list[str]
    methods: list[str]
    needs_review: bool


class QuestionTagUpdateRequest(BaseModel):
    knowledge_point_ids: list[int] = Field(default_factory=list)
    solution_method_ids: list[int] = Field(default_factory=list)


class ChatMessageRequest(BaseModel):
    session_id: int | None = None
    question_id: int
    content: str
    user_id: str | None = None


class ChatMessageResponse(ORMModel):
    id: int
    role: str
    content: str
    model_name: str | None = None
    token_usage: int | None = None


class ChatSessionResponse(TimestampedResponse):
    id: int
    user_id: str | None = None
    question_id: int
    title: str | None = None
    messages: list[ChatMessageResponse] = Field(default_factory=list)


class ChatSessionListItemResponse(TimestampedResponse):
    id: int
    user_id: str | None = None
    question_id: int
    title: str | None = None
    message_count: int = 0
    last_message_preview: str | None = None

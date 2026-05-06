from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.question import QuestionDetailResponse


class PracticeStateResponse(BaseModel):
    question_id: int
    practice_status: str = "NOT_STARTED"
    is_favorited: bool = False
    last_practiced_at: datetime | None = None
    solved_at: datetime | None = None


class PracticeStateUpdateRequest(BaseModel):
    practice_status: str | None = None
    is_favorited: bool | None = None


class PracticeQuestionResponse(BaseModel):
    question: QuestionDetailResponse
    practice_state: PracticeStateResponse
    match_count: int = 0


class PracticeSummaryItem(BaseModel):
    question_id: int
    paper_id: int
    paper_title: str
    question_no: str
    stem_text: str
    practice_status: str
    is_favorited: bool
    last_practiced_at: datetime | None = None
    solved_at: datetime | None = None


class PracticeSummaryResponse(BaseModel):
    in_progress_count: int = 0
    solved_count: int = 0
    favorite_count: int = 0
    recent_in_progress: list[PracticeSummaryItem] = Field(default_factory=list)
    recent_favorites: list[PracticeSummaryItem] = Field(default_factory=list)

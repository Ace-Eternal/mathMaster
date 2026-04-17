from pydantic import BaseModel, Field

from app.schemas.paper import PaperResponse
from app.schemas.question import QuestionDetailResponse


class PaperSearchParams(BaseModel):
    keyword: str | None = None
    year: int | None = None
    region: str | None = None
    grade_level: str | None = None
    term: str | None = None


class QuestionSearchParams(BaseModel):
    keyword: str | None = None
    question_type: str | None = None
    year: int | None = None
    knowledge_point_id: int | None = None
    solution_method_id: int | None = None
    page: int = 1
    page_size: int = 20


class SearchResponse(BaseModel):
    total: int
    items: list = Field(default_factory=list)

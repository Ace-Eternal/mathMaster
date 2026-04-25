from pydantic import BaseModel, Field


class PaperSearchItem(BaseModel):
    id: int
    title: str
    year: int | None = None
    region: str | None = None
    grade_level: str | None = None
    term: str | None = None
    status: str


class QuestionSearchItem(BaseModel):
    id: int
    paper_id: int
    paper_title: str
    question_no: str
    question_type: str | None = None
    stem_text: str
    review_status: str
    year: int | None = None
    region: str | None = None
    grade_level: str | None = None
    term: str | None = None
    has_answer: bool = False


class PaperSearchParams(BaseModel):
    keyword: str | None = None
    year: int | None = None
    region: str | None = None
    grade_level: str | None = None
    term: str | None = None


class QuestionSearchParams(BaseModel):
    keyword: str | None = None
    keyword_match_mode: str = "any"
    question_type: str | None = None
    year: int | None = None
    region: str | None = None
    grade_level: str | None = None
    term: str | None = None
    review_status: str | None = None
    has_answer: bool | None = None
    knowledge_point_id: int | None = None
    solution_method_id: int | None = None
    sort_by: str = "updated_desc"
    page: int = 1
    page_size: int = 20


class SearchResponse(BaseModel):
    total: int
    items: list[PaperSearchItem | QuestionSearchItem] = Field(default_factory=list)

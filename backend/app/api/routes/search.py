from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.search import SearchResponse
from app.services.search import SearchService

router = APIRouter()


@router.get("/papers", response_model=SearchResponse)
def search_papers(
    keyword: str | None = None,
    year: int | None = None,
    region: str | None = None,
    grade_level: str | None = None,
    term: str | None = None,
    db: Session = Depends(get_db),
):
    return SearchService(db).search_papers(keyword, year, region, grade_level, term)


@router.get("/questions", response_model=SearchResponse)
def search_questions(
    keyword: str | None = None,
    keyword_match_mode: str = Query(default="any", pattern="^(any|all)$"),
    question_type: str | None = None,
    year: int | None = None,
    region: str | None = None,
    grade_level: str | None = None,
    term: str | None = None,
    review_status: str | None = None,
    has_answer: bool | None = None,
    knowledge_point_id: int | None = None,
    solution_method_id: int | None = None,
    sort_by: str = Query(default="updated_desc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return SearchService(db).search_questions(
        keyword=keyword,
        keyword_match_mode=keyword_match_mode,
        question_type=question_type,
        year=year,
        region=region,
        grade_level=grade_level,
        term=term,
        review_status=review_status,
        has_answer=has_answer,
        knowledge_point_id=knowledge_point_id,
        solution_method_id=solution_method_id,
        sort_by=sort_by,
        page=page,
        page_size=page_size,
    )

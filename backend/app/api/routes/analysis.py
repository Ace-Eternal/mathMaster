import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import AnalysisRunResponse
from app.services.analysis import KnowledgeAnalysisService
from app.services.llm.gateway import LLMGateway

router = APIRouter()


def _normalize_name_list(values: list) -> list[str]:
    normalized: list[str] = []
    for item in values or []:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("label") or item.get("title") or "").strip()
        else:
            name = str(item or "").strip()
        if name:
            normalized.append(name)
    return normalized


@router.post("/questions/{question_id}", response_model=AnalysisRunResponse)
def analyze_question(question_id: int, db: Session = Depends(get_db)):
    analysis = KnowledgeAnalysisService(db, LLMGateway()).analyze_question(question_id)
    payload = json.loads(analysis.analysis_json)
    return AnalysisRunResponse(
        question_id=question_id,
        analysis_id=analysis.id,
        knowledges=_normalize_name_list(payload.get("major_knowledge_points", []))
        + _normalize_name_list(payload.get("minor_knowledge_points", [])),
        methods=_normalize_name_list(payload.get("solution_methods", [])),
        needs_review=payload.get("need_manual_review", False),
    )

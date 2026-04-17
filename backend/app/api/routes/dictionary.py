from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import KnowledgePoint, SolutionMethod
from app.schemas.dictionary import (
    KnowledgePointCreate,
    KnowledgePointResponse,
    SolutionMethodCreate,
    SolutionMethodResponse,
)

router = APIRouter()


@router.get("/knowledge-points", response_model=list[KnowledgePointResponse])
def list_knowledge_points(db: Session = Depends(get_db)):
    return list(db.execute(select(KnowledgePoint).order_by(KnowledgePoint.level, KnowledgePoint.sort_no)).scalars())


@router.post("/knowledge-points", response_model=KnowledgePointResponse)
def create_knowledge_point(payload: KnowledgePointCreate, db: Session = Depends(get_db)):
    item = KnowledgePoint(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/solution-methods", response_model=list[SolutionMethodResponse])
def list_solution_methods(db: Session = Depends(get_db)):
    return list(db.execute(select(SolutionMethod).order_by(SolutionMethod.name)).scalars())


@router.post("/solution-methods", response_model=SolutionMethodResponse)
def create_solution_method(payload: SolutionMethodCreate, db: Session = Depends(get_db)):
    item = SolutionMethod(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

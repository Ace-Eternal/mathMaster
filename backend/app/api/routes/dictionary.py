from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import KnowledgePoint, QuestionKnowledge, QuestionMethod, SolutionMethod
from app.schemas.dictionary import (
    KnowledgePointCreate,
    KnowledgePointResponse,
    KnowledgePointUpdate,
    SolutionMethodCreate,
    SolutionMethodResponse,
    SolutionMethodUpdate,
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


@router.patch("/knowledge-points/{knowledge_point_id}", response_model=KnowledgePointResponse)
def update_knowledge_point(knowledge_point_id: int, payload: KnowledgePointUpdate, db: Session = Depends(get_db)):
    item = db.get(KnowledgePoint, knowledge_point_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/knowledge-points/{knowledge_point_id}")
def delete_knowledge_point(knowledge_point_id: int, db: Session = Depends(get_db)):
    item = db.get(KnowledgePoint, knowledge_point_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    db.query(QuestionKnowledge).filter(QuestionKnowledge.knowledge_point_id == knowledge_point_id).delete()
    db.delete(item)
    db.commit()
    return {"ok": True}


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


@router.patch("/solution-methods/{solution_method_id}", response_model=SolutionMethodResponse)
def update_solution_method(solution_method_id: int, payload: SolutionMethodUpdate, db: Session = Depends(get_db)):
    item = db.get(SolutionMethod, solution_method_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Solution method not found")
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/solution-methods/{solution_method_id}")
def delete_solution_method(solution_method_id: int, db: Session = Depends(get_db)):
    item = db.get(SolutionMethod, solution_method_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Solution method not found")
    db.query(QuestionMethod).filter(QuestionMethod.solution_method_id == solution_method_id).delete()
    db.delete(item)
    db.commit()
    return {"ok": True}

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AppUser, KnowledgePoint, QuestionKnowledge, QuestionMethod, SolutionMethod
from app.schemas.dictionary import (
    KnowledgePointCreate,
    KnowledgePointResponse,
    KnowledgePointUpdate,
    SolutionMethodCreate,
    SolutionMethodResponse,
    SolutionMethodUpdate,
)
from app.services.audit import entity_summary, set_created_actor, set_updated_actor, write_audit_log
from app.services.auth import request_meta, require_permission

router = APIRouter()


@router.get("/knowledge-points", response_model=list[KnowledgePointResponse])
def list_knowledge_points(db: Session = Depends(get_db)):
    return list(db.execute(select(KnowledgePoint).order_by(KnowledgePoint.level, KnowledgePoint.sort_no)).scalars())


@router.post("/knowledge-points", response_model=KnowledgePointResponse)
def create_knowledge_point(
    payload: KnowledgePointCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("dictionary.manage")),
):
    item = KnowledgePoint(**payload.model_dump())
    set_created_actor(item, user)
    db.add(item)
    write_audit_log(db, actor=user, action="dictionary.knowledge.create", resource_type="knowledge_point", resource_id=None, after=payload.model_dump(), **request_meta(request))
    db.commit()
    db.refresh(item)
    return item


@router.patch("/knowledge-points/{knowledge_point_id}", response_model=KnowledgePointResponse)
def update_knowledge_point(
    knowledge_point_id: int,
    payload: KnowledgePointUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("dictionary.manage")),
):
    item = db.get(KnowledgePoint, knowledge_point_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    before = entity_summary(item, ["name", "level", "parent_id", "sort_no"])
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    set_updated_actor(item, user)
    db.add(item)
    write_audit_log(db, actor=user, action="dictionary.knowledge.update", resource_type="knowledge_point", resource_id=item.id, before=before, after=payload.model_dump(), **request_meta(request))
    db.commit()
    db.refresh(item)
    return item


@router.delete("/knowledge-points/{knowledge_point_id}")
def delete_knowledge_point(
    knowledge_point_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("dictionary.manage")),
):
    item = db.get(KnowledgePoint, knowledge_point_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge point not found")
    db.query(QuestionKnowledge).filter(QuestionKnowledge.knowledge_point_id == knowledge_point_id).delete()
    write_audit_log(db, actor=user, action="dictionary.knowledge.delete", resource_type="knowledge_point", resource_id=item.id, before=entity_summary(item, ["name", "level"]), **request_meta(request))
    db.delete(item)
    db.commit()
    return {"ok": True}


@router.get("/solution-methods", response_model=list[SolutionMethodResponse])
def list_solution_methods(db: Session = Depends(get_db)):
    return list(db.execute(select(SolutionMethod).order_by(SolutionMethod.name)).scalars())


@router.post("/solution-methods", response_model=SolutionMethodResponse)
def create_solution_method(
    payload: SolutionMethodCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("dictionary.manage")),
):
    item = SolutionMethod(**payload.model_dump())
    set_created_actor(item, user)
    db.add(item)
    write_audit_log(db, actor=user, action="dictionary.method.create", resource_type="solution_method", resource_id=None, after=payload.model_dump(), **request_meta(request))
    db.commit()
    db.refresh(item)
    return item


@router.patch("/solution-methods/{solution_method_id}", response_model=SolutionMethodResponse)
def update_solution_method(
    solution_method_id: int,
    payload: SolutionMethodUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("dictionary.manage")),
):
    item = db.get(SolutionMethod, solution_method_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Solution method not found")
    before = entity_summary(item, ["name", "description"])
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    set_updated_actor(item, user)
    db.add(item)
    write_audit_log(db, actor=user, action="dictionary.method.update", resource_type="solution_method", resource_id=item.id, before=before, after=payload.model_dump(), **request_meta(request))
    db.commit()
    db.refresh(item)
    return item


@router.delete("/solution-methods/{solution_method_id}")
def delete_solution_method(
    solution_method_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("dictionary.manage")),
):
    item = db.get(SolutionMethod, solution_method_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Solution method not found")
    db.query(QuestionMethod).filter(QuestionMethod.solution_method_id == solution_method_id).delete()
    write_audit_log(db, actor=user, action="dictionary.method.delete", resource_type="solution_method", resource_id=item.id, before=entity_summary(item, ["name"]), **request_meta(request))
    db.delete(item)
    db.commit()
    return {"ok": True}

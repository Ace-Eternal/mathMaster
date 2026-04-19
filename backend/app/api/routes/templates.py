from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import SolutionTemplate
from app.schemas.template import SolutionTemplateCreate, SolutionTemplateResponse, SolutionTemplateUpdate
from app.services.storage.factory import get_storage_service

router = APIRouter()


def _template_key(template_id: int) -> str:
    return f"templates/{template_id}/template.md"


def _save_template_file(template: SolutionTemplate) -> str:
    storage = get_storage_service()
    key = _template_key(template.id)
    storage.save_file((template.content or "").encode("utf-8"), key)
    return key


@router.get("", response_model=list[SolutionTemplateResponse])
def list_templates(keyword: str | None = None, db: Session = Depends(get_db)):
    stmt = select(SolutionTemplate).order_by(SolutionTemplate.updated_at.desc())
    normalized_keyword = (keyword or "").strip()
    if normalized_keyword:
        pattern = f"%{normalized_keyword}%"
        stmt = stmt.where(
            or_(
                SolutionTemplate.name.like(pattern),
                SolutionTemplate.description.like(pattern),
                SolutionTemplate.tags.like(pattern),
            )
        )
    return list(db.execute(stmt).scalars())


@router.get("/{template_id}", response_model=SolutionTemplateResponse)
def get_template(template_id: int, db: Session = Depends(get_db)):
    template = db.get(SolutionTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return template


@router.post("", response_model=SolutionTemplateResponse)
def create_template(payload: SolutionTemplateCreate, db: Session = Depends(get_db)):
    template = SolutionTemplate(**payload.model_dump())
    db.add(template)
    db.commit()
    db.refresh(template)

    saved_key: str | None = None
    try:
        saved_key = _save_template_file(template)
        template.template_md_path = saved_key
        db.add(template)
        db.commit()
        db.refresh(template)
        return template
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if saved_key:
            try:
                get_storage_service().delete_file(saved_key)
            except Exception:
                pass
        db.delete(template)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Template file sync failed: {exc}") from exc


@router.patch("/{template_id}", response_model=SolutionTemplateResponse)
def update_template(template_id: int, payload: SolutionTemplateUpdate, db: Session = Depends(get_db)):
    template = db.get(SolutionTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    data = payload.model_dump(exclude_unset=True)
    if data.get("name") is None and "name" in data:
        raise HTTPException(status_code=422, detail="Template name cannot be null")
    if data.get("content") is None and "content" in data:
        raise HTTPException(status_code=422, detail="Template content cannot be null")

    content_changed = "content" in data
    old_content = template.content
    old_path = template.template_md_path
    for field, value in data.items():
        setattr(template, field, value)

    try:
        if content_changed:
            template.template_md_path = _save_template_file(template)
        db.add(template)
        db.commit()
        db.refresh(template)
        return template
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if content_changed and old_path:
            try:
                get_storage_service().save_file((old_content or "").encode("utf-8"), old_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Template file sync failed: {exc}") from exc


@router.delete("/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    template = db.get(SolutionTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    try:
        if template.template_md_path:
            get_storage_service().delete_file(template.template_md_path)
        db.delete(template)
        db.commit()
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Template delete failed: {exc}") from exc

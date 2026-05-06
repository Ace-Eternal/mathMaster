from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AppUser, AuditLog
from app.schemas.auth import AuditLogResponse
from app.services.auth import require_permission

router = APIRouter()


@router.get("", response_model=list[AuditLogResponse])
def list_audit_logs(
    action: str | None = None,
    resource_type: str | None = None,
    actor_user_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    _user: AppUser = Depends(require_permission("audit.read")),
):
    stmt = select(AuditLog, AppUser.username).outerjoin(AppUser, AppUser.id == AuditLog.actor_user_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if actor_user_id:
        stmt = stmt.where(AuditLog.actor_user_id == actor_user_id)
    rows = db.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit)).all()
    return [
        AuditLogResponse(
            id=log.id,
            actor_user_id=log.actor_user_id,
            actor_username=username,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            before_summary_json=log.before_summary_json,
            after_summary_json=log.after_summary_json,
            ip_address=log.ip_address,
            user_agent=log.user_agent,
            created_at=log.created_at,
        )
        for log, username in rows
    ]

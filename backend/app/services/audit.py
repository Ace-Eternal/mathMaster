from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models import AppUser, AuditLog


def compact_summary(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, default=str)


def write_audit_log(
    db: Session,
    *,
    actor: AppUser | None,
    action: str,
    resource_type: str,
    resource_id: int | str | None,
    before: Any = None,
    after: Any = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=str(resource_id) if resource_id is not None else None,
            before_summary_json=compact_summary(before),
            after_summary_json=compact_summary(after),
            ip_address=ip_address,
            user_agent=user_agent,
        )
    )


def set_created_actor(target: Any, actor: AppUser | None) -> None:
    if actor is None:
        return
    if hasattr(target, "created_by_user_id") and getattr(target, "created_by_user_id", None) is None:
        setattr(target, "created_by_user_id", actor.id)
    if hasattr(target, "updated_by_user_id"):
        setattr(target, "updated_by_user_id", actor.id)


def set_updated_actor(target: Any, actor: AppUser | None) -> None:
    if actor is None:
        return
    if hasattr(target, "updated_by_user_id"):
        setattr(target, "updated_by_user_id", actor.id)


def entity_summary(target: Any, fields: list[str]) -> dict[str, Any]:
    return {field: getattr(target, field, None) for field in fields}

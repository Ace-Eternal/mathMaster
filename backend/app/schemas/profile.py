from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.auth import UserResponse


class PagedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[dict[str, Any]] = Field(default_factory=list)


class ProfileSummaryResponse(BaseModel):
    user: UserResponse
    paper_count: int = 0
    revised_question_count: int = 0
    practice_count: int = 0
    favorite_count: int = 0
    chat_session_count: int = 0
    audit_count: int = 0


class AuditGroupResponse(BaseModel):
    group: str
    label: str
    total: int
    items: list[dict[str, Any]] = Field(default_factory=list)

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AppUser
from app.schemas.profile import AuditGroupResponse, PagedResponse, ProfileSummaryResponse
from app.services.auth import require_permission
from app.services.profile import ProfileService

router = APIRouter()


def _page(page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100)):
    return page, page_size


@router.get("/summary", response_model=ProfileSummaryResponse)
def summary(db: Session = Depends(get_db), user: AppUser = Depends(require_permission("profile.read"))):
    return ProfileService(db).summary(user)


@router.get("/papers", response_model=PagedResponse)
def papers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("profile.read")),
):
    return ProfileService(db).papers(user, page=page, page_size=page_size)


@router.get("/revised-questions", response_model=PagedResponse)
def revised_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("profile.read")),
):
    return ProfileService(db).revised_questions(user, page=page, page_size=page_size)


@router.get("/practice-questions", response_model=PagedResponse)
def practice_questions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("profile.read")),
):
    return ProfileService(db).practice_questions(user, page=page, page_size=page_size)


@router.get("/favorites", response_model=PagedResponse)
def favorites(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("profile.read")),
):
    return ProfileService(db).practice_questions(user, page=page, page_size=page_size, favorites_only=True)


@router.get("/chat-sessions", response_model=PagedResponse)
def chat_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("profile.read")),
):
    return ProfileService(db).chat_sessions(user, page=page, page_size=page_size)


@router.get("/audit-groups", response_model=list[AuditGroupResponse])
def audit_groups(
    limit_per_group: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: AppUser = Depends(require_permission("profile.read")),
):
    return ProfileService(db).audit_groups(user, limit_per_group=limit_per_group)

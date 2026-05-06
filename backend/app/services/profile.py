from __future__ import annotations

from sqlalchemy import String, func, select
from sqlalchemy.orm import Session

from app.models import AppUser, AuditLog, ChatMessage, ChatSession, Paper, Question, UserQuestionState
from app.schemas.profile import AuditGroupResponse, PagedResponse, ProfileSummaryResponse
from app.services.auth import build_user_response


QUESTION_REVISION_ACTIONS = {"question.create", "question.update", "question.review_update", "question.delete"}

AUDIT_GROUPS = {
    "upload": ("上传", ["paper.upload", "paper.import_folder"]),
    "paper": ("试卷修改", ["paper.update", "paper.bind_answer", "paper.unbind_answer", "paper.delete", "paper.restore"]),
    "question": ("题目修订", sorted(QUESTION_REVISION_ACTIONS)),
    "practice": ("刷题", ["practice.update_state"]),
    "chat": ("对话", ["chat.send", "chat.update", "chat.delete"]),
    "content": ("字典模板", ["dictionary.", "template."]),
    "user": ("用户管理", ["user."]),
}


class ProfileService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def summary(self, user: AppUser) -> ProfileSummaryResponse:
        return ProfileSummaryResponse(
            user=build_user_response(self.db, user),
            paper_count=self._count(select(Paper.id).where(Paper.created_by_user_id == user.id, Paper.is_deleted.is_(False))),
            revised_question_count=self._count_revised_questions(user.id),
            practice_count=self._count(select(UserQuestionState.id).where(UserQuestionState.user_id == user.id)),
            favorite_count=self._count(select(UserQuestionState.id).where(UserQuestionState.user_id == user.id, UserQuestionState.is_favorited.is_(True))),
            chat_session_count=self._count(select(ChatSession.id).where(ChatSession.user_id == str(user.id))),
            audit_count=self._count(select(AuditLog.id).where(AuditLog.actor_user_id == user.id)),
        )

    def papers(self, user: AppUser, *, page: int, page_size: int) -> PagedResponse:
        stmt = select(Paper).where(Paper.created_by_user_id == user.id, Paper.is_deleted.is_(False)).order_by(Paper.updated_at.desc())
        total = self._count(select(Paper.id).where(Paper.created_by_user_id == user.id, Paper.is_deleted.is_(False)))
        rows = self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).scalars()
        return self._paged(total, page, page_size, [
            {
                "paper_id": paper.id,
                "title": paper.title,
                "year": paper.year,
                "region": paper.region,
                "grade_level": paper.grade_level,
                "term": paper.term,
                "status": paper.status,
                "created_at": paper.created_at,
                "updated_at": paper.updated_at,
            }
            for paper in rows
        ])

    def revised_questions(self, user: AppUser, *, page: int, page_size: int) -> PagedResponse:
        latest = (
            select(AuditLog.resource_id, func.max(AuditLog.created_at).label("last_at"))
            .where(
                AuditLog.actor_user_id == user.id,
                AuditLog.resource_type == "question",
                AuditLog.action.in_(QUESTION_REVISION_ACTIONS),
            )
            .group_by(AuditLog.resource_id)
            .subquery()
        )
        stmt = (
            select(Question, Paper, latest.c.last_at)
            .join(latest, latest.c.resource_id == func.cast(Question.id, String))
            .join(Paper, Paper.id == Question.paper_id)
            .where(Paper.is_deleted.is_(False))
            .order_by(latest.c.last_at.desc())
        )
        total = self.db.execute(select(func.count()).select_from(latest)).scalar_one()
        rows = self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
        return self._paged(total, page, page_size, [
            {
                "question_id": question.id,
                "paper_id": paper.id,
                "paper_title": paper.title,
                "question_no": question.question_no,
                "question_type": question.question_type,
                "stem_text": question.stem_text,
                "review_status": question.review_status,
                "last_revised_at": last_at,
            }
            for question, paper, last_at in rows
        ])

    def practice_questions(self, user: AppUser, *, page: int, page_size: int, favorites_only: bool = False) -> PagedResponse:
        base = (
            select(UserQuestionState, Question, Paper)
            .join(Question, Question.id == UserQuestionState.question_id)
            .join(Paper, Paper.id == Question.paper_id)
            .where(UserQuestionState.user_id == user.id, Paper.is_deleted.is_(False))
        )
        count_stmt = (
            select(UserQuestionState.id)
            .join(Question, Question.id == UserQuestionState.question_id)
            .join(Paper, Paper.id == Question.paper_id)
            .where(UserQuestionState.user_id == user.id, Paper.is_deleted.is_(False))
        )
        if favorites_only:
            base = base.where(UserQuestionState.is_favorited.is_(True))
            count_stmt = count_stmt.where(UserQuestionState.is_favorited.is_(True))
        total = self._count(count_stmt)
        rows = self.db.execute(base.order_by(UserQuestionState.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return self._paged(total, page, page_size, [
            {
                "question_id": question.id,
                "paper_id": paper.id,
                "paper_title": paper.title,
                "question_no": question.question_no,
                "stem_text": question.stem_text,
                "practice_status": state.practice_status,
                "is_favorited": state.is_favorited,
                "last_practiced_at": state.last_practiced_at,
                "solved_at": state.solved_at,
                "updated_at": state.updated_at,
            }
            for state, question, paper in rows
        ])

    def chat_sessions(self, user: AppUser, *, page: int, page_size: int) -> PagedResponse:
        total = self._count(select(ChatSession.id).where(ChatSession.user_id == str(user.id)))
        stmt = (
            select(ChatSession, Question)
            .join(Question, Question.id == ChatSession.question_id)
            .where(ChatSession.user_id == str(user.id))
            .order_by(ChatSession.updated_at.desc())
        )
        rows = self.db.execute(stmt.offset((page - 1) * page_size).limit(page_size)).all()
        items = []
        for session, question in rows:
            message_count = self.db.execute(select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session.id)).scalar_one()
            last_message = self.db.execute(
                select(ChatMessage).where(ChatMessage.session_id == session.id).order_by(ChatMessage.id.desc()).limit(1)
            ).scalar_one_or_none()
            items.append(
                {
                    "session_id": session.id,
                    "question_id": question.id,
                    "question_no": question.question_no,
                    "title": session.title,
                    "message_count": message_count,
                    "last_message_preview": last_message.content[:100] if last_message else None,
                    "updated_at": session.updated_at,
                }
            )
        return self._paged(total, page, page_size, items)

    def audit_groups(self, user: AppUser, *, limit_per_group: int = 10) -> list[AuditGroupResponse]:
        groups: list[AuditGroupResponse] = []
        for group, (label, patterns) in AUDIT_GROUPS.items():
            stmt = select(AuditLog).where(AuditLog.actor_user_id == user.id)
            conditions = []
            for pattern in patterns:
                if pattern.endswith("."):
                    conditions.append(AuditLog.action.like(f"{pattern}%"))
                else:
                    conditions.append(AuditLog.action == pattern)
            if conditions:
                from sqlalchemy import or_

                stmt = stmt.where(or_(*conditions))
            total = self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()
            logs = self.db.execute(stmt.order_by(AuditLog.created_at.desc()).limit(limit_per_group)).scalars()
            groups.append(
                AuditGroupResponse(
                    group=group,
                    label=label,
                    total=total,
                    items=[self._audit_item(log) for log in logs],
                )
            )
        other_stmt = select(AuditLog).where(AuditLog.actor_user_id == user.id)
        known_actions = [action for _, actions in AUDIT_GROUPS.values() for action in actions if not action.endswith(".")]
        known_prefixes = [action for _, actions in AUDIT_GROUPS.values() for action in actions if action.endswith(".")]
        if known_actions:
            other_stmt = other_stmt.where(AuditLog.action.notin_(known_actions))
        for prefix in known_prefixes:
            other_stmt = other_stmt.where(AuditLog.action.not_like(f"{prefix}%"))
        other_total = self.db.execute(select(func.count()).select_from(other_stmt.subquery())).scalar_one()
        other_logs = self.db.execute(other_stmt.order_by(AuditLog.created_at.desc()).limit(limit_per_group)).scalars()
        groups.append(AuditGroupResponse(group="other", label="其他", total=other_total, items=[self._audit_item(log) for log in other_logs]))
        return groups

    @staticmethod
    def _paged(total: int, page: int, page_size: int, items: list[dict]) -> PagedResponse:
        return PagedResponse(total=total, page=page, page_size=page_size, items=items)

    def _count(self, stmt) -> int:
        return self.db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one()

    def _count_revised_questions(self, user_id: int) -> int:
        return self.db.execute(
            select(func.count(func.distinct(AuditLog.resource_id))).where(
                AuditLog.actor_user_id == user_id,
                AuditLog.resource_type == "question",
                AuditLog.action.in_(QUESTION_REVISION_ACTIONS),
            )
        ).scalar_one()

    @staticmethod
    def _audit_item(log: AuditLog) -> dict:
        return {
            "audit_log_id": log.id,
            "action": log.action,
            "resource_type": log.resource_type,
            "resource_id": log.resource_id,
            "before_summary_json": log.before_summary_json,
            "after_summary_json": log.after_summary_json,
            "created_at": log.created_at,
        }

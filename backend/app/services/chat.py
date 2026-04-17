from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ChatMessage, ChatSession, Question
from app.services.llm.gateway import LLMGateway


class ChatTutorService:
    def __init__(self, db: Session, llm_gateway: LLMGateway) -> None:
        self.db = db
        self.llm_gateway = llm_gateway
        self.system_prompt = Path(__file__).resolve().parent.joinpath("prompts", "chat_system_prompt.md").read_text(
            encoding="utf-8"
        )

    def send(
        self,
        *,
        question_id: int,
        content: str,
        user_id: str | None = None,
        session_id: int | None = None,
    ) -> ChatSession:
        question = self.db.execute(
            select(Question).options(selectinload(Question.answer), selectinload(Question.analysis)).where(Question.id == question_id)
        ).scalar_one()
        session = (
            self.db.execute(select(ChatSession).options(selectinload(ChatSession.messages)).where(ChatSession.id == session_id)).scalar_one_or_none()
            if session_id
            else None
        )
        if not session:
            session = ChatSession(question_id=question_id, user_id=user_id, title=f"Question {question.question_no}")
            self.db.add(session)
            self.db.flush()

        self.db.add(ChatMessage(session_id=session.id, role="user", content=content))
        self.db.flush()
        session = self.db.execute(
            select(ChatSession).options(selectinload(ChatSession.messages)).where(ChatSession.id == session.id)
        ).scalar_one()
        history = [{"role": message.role, "content": message.content} for message in session.messages]
        context_prefix = (
            f"Question No: {question.question_no}\n"
            f"Stem: {question.stem_text}\n"
            f"Answer: {question.answer.answer_text if question.answer else 'N/A'}\n"
            f"Analysis: {question.analysis.explanation_md if question.analysis else 'N/A'}"
        )
        result = self.llm_gateway.chat(
            system_prompt=self.system_prompt,
            messages=[{"role": "system", "content": context_prefix}, *history],
        )
        self.db.add(
            ChatMessage(
                session_id=session.id,
                role="assistant",
                content=result["content"],
                model_name=result["model_name"],
                token_usage=result["token_usage"],
            )
        )
        self.db.commit()
        return self.db.execute(
            select(ChatSession).options(selectinload(ChatSession.messages)).where(ChatSession.id == session.id)
        ).scalar_one()

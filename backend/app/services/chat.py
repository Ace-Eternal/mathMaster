from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ChatMessage, ChatSession, Question
from app.services.llm.gateway import LLMGateway
from app.services.storage.factory import get_storage_service


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
        question = self._load_question(question_id)
        session = self._ensure_session(question=question, session_id=session_id, user_id=user_id)
        self._append_user_message(session=session, content=content)
        self.db.flush()
        session = self._load_session(session.id)
        history = [{"role": message.role, "content": message.content} for message in session.messages]
        multimodal_context = self._build_multimodal_context(
            question=question,
            context_prefix=self._build_context_prefix(question),
        )
        result = self.llm_gateway.chat(
            system_prompt=self._build_system_prompt(),
            messages=[
                {
                    "role": "user",
                    "content": multimodal_context,
                },
                *history,
            ],
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
        return self._load_session(session.id)

    def stream_send(
        self,
        *,
        question_id: int,
        content: str,
        user_id: str | None = None,
        session_id: int | None = None,
    ) -> tuple[int, Iterator[dict[str, Any]]]:
        question = self._load_question(question_id)
        session = self._ensure_session(question=question, session_id=session_id, user_id=user_id)
        self._append_user_message(session=session, content=content)
        self.db.commit()
        session = self._load_session(session.id)
        history = [{"role": message.role, "content": message.content} for message in session.messages]
        multimodal_context = self._build_multimodal_context(
            question=question,
            context_prefix=self._build_context_prefix(question),
        )

        def event_iter() -> Iterator[dict[str, Any]]:
            assistant_parts: list[str] = []
            model_name: str | None = None
            try:
                yield {"type": "meta", "session_id": session.id}
                for event in self.llm_gateway.stream_chat(
                    system_prompt=self._build_system_prompt(),
                    messages=[
                        {
                            "role": "user",
                            "content": multimodal_context,
                        },
                        *history,
                    ],
                ):
                    if event.get("type") == "start":
                        model_name = str(event.get("model_name") or "") or None
                        yield event
                        continue
                    if event.get("type") == "chunk":
                        chunk = str(event.get("content") or "")
                        assistant_parts.append(chunk)
                        yield {"type": "chunk", "content": chunk}
                assistant_message = ChatMessage(
                    session_id=session.id,
                    role="assistant",
                    content="".join(assistant_parts).strip(),
                    model_name=model_name,
                    token_usage=None,
                )
                self.db.add(assistant_message)
                self.db.commit()
                self.db.refresh(assistant_message)
                yield {
                    "type": "done",
                    "session_id": session.id,
                    "message_id": assistant_message.id,
                    "model_name": model_name,
                }
            except Exception as exc:  # noqa: BLE001
                self.db.rollback()
                yield {"type": "error", "message": str(exc)}

        return session.id, event_iter()

    def _load_question(self, question_id: int) -> Question:
        return self.db.execute(
            select(Question).options(selectinload(Question.answer), selectinload(Question.analysis)).where(Question.id == question_id)
        ).scalar_one()

    def list_sessions(self, *, question_id: int) -> list[ChatSession]:
        return list(
            self.db.execute(
                select(ChatSession)
                .options(selectinload(ChatSession.messages))
                .where(ChatSession.question_id == question_id)
                .order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
            ).scalars()
        )

    def get_session(self, *, session_id: int, question_id: int | None = None) -> ChatSession:
        session = self._load_session(session_id)
        if question_id is not None and session.question_id != question_id:
            raise ValueError("Chat session not found for question")
        return session

    def _ensure_session(self, *, question: Question, session_id: int | None, user_id: str | None) -> ChatSession:
        session = (
            self.db.execute(select(ChatSession).options(selectinload(ChatSession.messages)).where(ChatSession.id == session_id)).scalar_one_or_none()
            if session_id
            else None
        )
        if session:
            return session
        session = ChatSession(question_id=question.id, user_id=user_id, title=f"Question {question.question_no}")
        self.db.add(session)
        self.db.flush()
        return session

    def _load_session(self, session_id: int) -> ChatSession:
        return self.db.execute(
            select(ChatSession).options(selectinload(ChatSession.messages)).where(ChatSession.id == session_id)
        ).scalar_one()

    def _append_user_message(self, *, session: ChatSession, content: str) -> None:
        normalized_content = content.strip()
        self.db.add(ChatMessage(session_id=session.id, role="user", content=normalized_content))
        current_title = (session.title or "").strip()
        if not current_title or current_title.startswith("Question "):
            session.title = normalized_content[:40]
        self.db.add(session)

    @staticmethod
    def _build_context_prefix(question: Question) -> str:
        return (
            f"Question No: {question.question_no}\n"
            f"Stem: {question.stem_text}\n"
            f"Answer: {question.answer.answer_text if question.answer else 'N/A'}\n"
            f"Analysis: {question.analysis.explanation_md if question.analysis else 'N/A'}"
        )

    def _build_system_prompt(self) -> str:
        return (
            f"{self.system_prompt}\n\n"
            "你已经拿到了完整题目上下文，不要要求用户重复发送题目，不要谈代码、bug、功能开发。"
            "请直接围绕当前数学题进行教学式讲解。"
        )

    def _build_multimodal_context(self, *, question: Question, context_prefix: str) -> list[dict[str, Any]]:
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": "以下是当前题目的完整上下文，请你记住并仅围绕这些信息回答后续问题：\n" + context_prefix,
            }
        ]
        for image_part in self._load_question_image_parts(question=question):
            content.append(image_part)
        return content

    def _load_question_image_parts(self, *, question: Question) -> list[dict[str, Any]]:
        storage = get_storage_service()
        image_parts: list[dict[str, Any]] = []
        for json_path in [question.question_json_path, question.answer.answer_json_path if question.answer else None]:
            if not json_path or not storage.exists(json_path):
                continue
            try:
                document = json.loads(storage.read_file(json_path).decode("utf-8"))
            except Exception:
                continue
            for raw_src in self._extract_image_sources(document)[:4]:
                image_part = self._build_image_part(storage=storage, base_key=json_path, raw_src=raw_src)
                if image_part:
                    image_parts.append(image_part)
            if len(image_parts) >= 4:
                break
        return image_parts[:4]

    @staticmethod
    def _extract_image_sources(document: dict[str, Any]) -> list[str]:
        candidates: list[str] = []
        for item in (document.get("image_refs") or document.get("image_blocks") or []):
            raw_src = str(item.get("src") or item.get("img_path") or item.get("image_path") or "").strip()
            if raw_src and raw_src not in candidates:
                candidates.append(raw_src)
        for block in document.get("blocks") or []:
            raw_src = str(block.get("src") or block.get("img_path") or block.get("image_path") or "").strip()
            if raw_src and raw_src not in candidates:
                candidates.append(raw_src)
        return candidates

    def _build_image_part(self, *, storage, base_key: str, raw_src: str) -> dict[str, Any] | None:
        for candidate in self._build_candidate_keys(base_key=base_key, raw_src=raw_src):
            if not storage.exists(candidate):
                continue
            file_bytes = storage.read_file(candidate)
            mime_type = mimetypes.guess_type(candidate)[0] or "image/jpeg"
            data_url = f"data:{mime_type};base64,{base64.b64encode(file_bytes).decode('ascii')}"
            return {
                "type": "image_url",
                "image_url": data_url,
            }
        return None

    @staticmethod
    def _build_candidate_keys(*, base_key: str, raw_src: str) -> list[str]:
        normalized_src = raw_src.replace("\\", "/").lstrip("/")
        candidates: list[str] = [normalized_src]
        base_path = Path(base_key.replace("\\", "/").lstrip("/"))
        base_dir = base_path.parent.as_posix()
        if base_dir:
            candidates.append(f"{base_dir}/{normalized_src}")
            parts = base_dir.split("/")
            if parts[:1] == ["slices"] and len(parts) >= 2:
                candidates.append(f"mineu/{parts[1]}/{normalized_src}")
        unique: list[str] = []
        for candidate in candidates:
            if candidate not in unique:
                unique.append(candidate)
        return unique

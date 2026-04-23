import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import (
    ChatMessageRequest,
    ChatModelOptionResponse,
    ChatSessionListItemResponse,
    ChatSessionModelUpdateRequest,
    ChatSessionResponse,
)
from app.services.chat import ChatTutorService
from app.services.llm.gateway import LLMGateway

router = APIRouter()


@router.get("/questions/{question_id}/sessions", response_model=list[ChatSessionListItemResponse])
def list_sessions(question_id: int, db: Session = Depends(get_db)):
    service = ChatTutorService(db, LLMGateway())
    sessions = service.list_sessions(question_id=question_id)
    items = []
    for session in sessions:
        last_message = session.messages[-1] if session.messages else None
        items.append(
            ChatSessionListItemResponse(
                id=session.id,
                user_id=session.user_id,
                question_id=session.question_id,
                title=session.title,
                selected_model=session.selected_model,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=len(session.messages),
                last_message_preview=(last_message.content[:80] if last_message and last_message.content else None),
            )
        )
    return items


@router.get("/sessions/{session_id}", response_model=ChatSessionResponse)
def get_session(session_id: int, question_id: int | None = None, db: Session = Depends(get_db)):
    service = ChatTutorService(db, LLMGateway())
    try:
        session = service.get_session(session_id=session_id, question_id=question_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatSessionResponse.model_validate(session)


@router.post("/sessions/message", response_model=ChatSessionResponse)
def send_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    session = ChatTutorService(db, LLMGateway()).send(
        question_id=payload.question_id,
        content=payload.content,
        user_id=payload.user_id,
        session_id=payload.session_id,
        model_name=payload.model_name,
    )
    return ChatSessionResponse.model_validate(session)


@router.post("/sessions/message/stream")
def stream_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    _, event_iter = ChatTutorService(db, LLMGateway()).stream_send(
        question_id=payload.question_id,
        content=payload.content,
        user_id=payload.user_id,
        session_id=payload.session_id,
        model_name=payload.model_name,
    )

    def sse_iter():
        for event in event_iter:
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(sse_iter(), media_type="text/event-stream")


@router.post("/generations/{generation_id}/cancel")
def cancel_generation(generation_id: str, db: Session = Depends(get_db)):
    service = ChatTutorService(db, LLMGateway())
    try:
        return service.cancel_generation(generation_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/models", response_model=list[ChatModelOptionResponse])
def list_chat_models(db: Session = Depends(get_db)):
    return ChatTutorService(db, LLMGateway()).list_chat_models()


@router.patch("/sessions/{session_id}/model", response_model=ChatSessionResponse)
def update_session_model(session_id: int, payload: ChatSessionModelUpdateRequest, db: Session = Depends(get_db)):
    try:
        session = ChatTutorService(db, LLMGateway()).update_session_model(
            session_id=session_id,
            model_name=payload.model_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ChatSessionResponse.model_validate(session)


@router.delete("/sessions/{session_id}")
def delete_session(session_id: int, question_id: int | None = None, db: Session = Depends(get_db)):
    service = ChatTutorService(db, LLMGateway())
    try:
        service.delete_session(session_id=session_id, question_id=question_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"ok": True, "session_id": session_id}


@router.delete("/questions/{question_id}/sessions")
def clear_question_sessions(question_id: int, db: Session = Depends(get_db)):
    deleted_count = ChatTutorService(db, LLMGateway()).clear_sessions(question_id=question_id)
    return {"ok": True, "question_id": question_id, "deleted_count": deleted_count}

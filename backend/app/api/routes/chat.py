from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.question import ChatMessageRequest, ChatSessionResponse
from app.services.chat import ChatTutorService
from app.services.llm.gateway import LLMGateway

router = APIRouter()


@router.post("/sessions/message", response_model=ChatSessionResponse)
def send_message(payload: ChatMessageRequest, db: Session = Depends(get_db)):
    session = ChatTutorService(db, LLMGateway()).send(
        question_id=payload.question_id,
        content=payload.content,
        user_id=payload.user_id,
        session_id=payload.session_id,
    )
    return ChatSessionResponse.model_validate(session)

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AppUser
from app.schemas.auth import LoginRequest, LoginResponse, UserResponse
from app.services.auth import authenticate_user, build_user_response, create_access_token, get_current_user

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    return LoginResponse(access_token=create_access_token(user), user=build_user_response(db, user))


@router.get("/me", response_model=UserResponse)
def me(user: AppUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_user_response(db, user)


@router.post("/logout")
def logout():
    return {"ok": True}

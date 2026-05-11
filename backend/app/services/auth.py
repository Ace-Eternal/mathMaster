from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import AppUser, Role, RolePermission, UserPermission, UserRole
from app.schemas.auth import UserResponse


ALL_PERMISSIONS = [
    "profile.read",
    "paper.read",
    "paper.upload",
    "paper.edit",
    "paper.delete",
    "paper.run_pipeline",
    "question.read",
    "question.create",
    "question.edit",
    "question.delete",
    "task.read",
    "review.submit",
    "dictionary.manage",
    "template.manage",
    "chat.use",
    "practice.use",
    "audit.read",
    "user.manage",
]

ROLE_TEMPLATES: dict[str, dict[str, object]] = {
    "SUPER_ADMIN": {
        "name": "超级管理员",
        "description": "拥有全部权限，并可进入用户管理。",
        "permissions": ["*"],
    },
    "STUDENT": {
        "name": "学生",
        "description": "用于刷题、收藏、讲题对话和个人中心。",
        "permissions": ["profile.read", "paper.read", "question.read", "practice.use", "chat.use"],
    },
    "TEACHER": {
        "name": "教师",
        "description": "可上传试卷、审核、编辑题目并运行分析。",
        "permissions": [
            "profile.read",
            "paper.read",
            "question.read",
            "task.read",
            "practice.use",
            "chat.use",
            "paper.upload",
            "paper.edit",
            "paper.run_pipeline",
            "question.create",
            "question.edit",
            "question.delete",
            "review.submit",
        ],
    },
    "CONTENT_ADMIN": {
        "name": "内容管理员",
        "description": "可管理题库内容、字典和模板，但不是超级管理员。",
        "permissions": [
            "profile.read",
            "paper.read",
            "question.read",
            "task.read",
            "practice.use",
            "chat.use",
            "paper.upload",
            "paper.edit",
            "paper.delete",
            "paper.run_pipeline",
            "question.create",
            "question.edit",
            "question.delete",
            "review.submit",
            "dictionary.manage",
            "template.manage",
            "audit.read",
        ],
    },
}

PERMISSION_GROUPS = [
    {
        "code": "learning",
        "name": "学习对话",
        "permissions": [
            {"code": "profile.read", "name": "查看个人中心"},
            {"code": "paper.read", "name": "查看试卷列表"},
            {"code": "question.read", "name": "查看题目与答案"},
            {"code": "practice.use", "name": "随机刷题与收藏"},
            {"code": "chat.use", "name": "讲题对话"},
        ],
    },
    {
        "code": "paper",
        "name": "试卷",
        "permissions": [
            {"code": "paper.upload", "name": "上传/导入试卷"},
            {"code": "paper.edit", "name": "编辑试卷与答案"},
            {"code": "paper.delete", "name": "删除试卷"},
            {"code": "paper.run_pipeline", "name": "运行试卷流程"},
            {"code": "task.read", "name": "查看处理任务"},
        ],
    },
    {
        "code": "question",
        "name": "题目审核",
        "permissions": [
            {"code": "question.create", "name": "新增题目"},
            {"code": "question.edit", "name": "编辑题目"},
            {"code": "question.delete", "name": "删除题目"},
            {"code": "review.submit", "name": "提交审核"},
        ],
    },
    {
        "code": "content",
        "name": "字典模板",
        "permissions": [
            {"code": "dictionary.manage", "name": "管理知识点和解法"},
            {"code": "template.manage", "name": "管理解题模板"},
        ],
    },
    {
        "code": "admin",
        "name": "审计与用户",
        "permissions": [
            {"code": "audit.read", "name": "查看审计记录"},
            {"code": "user.manage", "name": "用户管理权限点"},
        ],
    },
]


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 240_000)
    return f"pbkdf2_sha256$240000${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
        return hmac.compare_digest(digest.hex(), expected)
    except ValueError:
        return False


def _sign_token(payload: dict[str, object]) -> str:
    raw_payload = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    body = base64.urlsafe_b64encode(raw_payload).decode("ascii").rstrip("=")
    signature = hmac.new(settings.auth_secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    sig = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{body}.{sig}"


def _decode_token(token: str) -> dict[str, object]:
    try:
        body, sig = token.split(".", 1)
        expected = hmac.new(settings.auth_secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(sig + "=" * (-len(sig) % 4))
        if not hmac.compare_digest(actual, expected):
            raise ValueError("bad signature")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc
    expires_at = datetime.fromisoformat(str(payload.get("exp")))
    if expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    return payload


def create_access_token(user: AppUser) -> str:
    return _sign_token(
        {
            "sub": user.id,
            "username": user.username,
            "exp": (datetime.utcnow() + timedelta(hours=settings.auth_token_expire_hours)).isoformat(),
        }
    )


def bootstrap_auth_data(db: Session) -> None:
    roles_by_code: dict[str, Role] = {}
    for code, template in ROLE_TEMPLATES.items():
        role = db.execute(select(Role).where(Role.code == code)).scalar_one_or_none()
        if role is None:
            role = Role(code=code, name=str(template["name"]), description=str(template["description"]))
            db.add(role)
            db.flush()
        else:
            role.name = str(template["name"])
            role.description = str(template["description"])
            db.add(role)
        roles_by_code[code] = role
        existing_permissions = {
            item.permission
            for item in db.execute(select(RolePermission).where(RolePermission.role_id == role.id)).scalars()
        }
        for permission in template["permissions"]:  # type: ignore[index]
            if permission not in existing_permissions:
                db.add(RolePermission(role_id=role.id, permission=str(permission)))

    user = db.execute(select(AppUser).where(AppUser.username == settings.bootstrap_admin_username)).scalar_one_or_none()
    if user is None:
        user = AppUser(
            username=settings.bootstrap_admin_username,
            display_name=settings.bootstrap_admin_display_name,
            password_hash=hash_password(settings.bootstrap_admin_password),
            status="ACTIVE",
        )
        db.add(user)
        db.flush()
    linked = db.execute(select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == roles_by_code["SUPER_ADMIN"].id)).scalar_one_or_none()
    if linked is None:
        db.add(UserRole(user_id=user.id, role_id=roles_by_code["SUPER_ADMIN"].id))

    user_ids_with_roles = {item for item in db.execute(select(UserRole.user_id)).scalars()}
    student_role = roles_by_code["STUDENT"]
    for existing_user in db.execute(select(AppUser)).scalars():
        if existing_user.id not in user_ids_with_roles:
            db.add(UserRole(user_id=existing_user.id, role_id=student_role.id))
    db.commit()


def user_permissions(db: Session, user_id: int) -> tuple[list[str], list[str]]:
    role_rows = db.execute(
        select(Role.code, RolePermission.permission)
        .join(UserRole, UserRole.role_id == Role.id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .where(UserRole.user_id == user_id)
    ).all()
    direct_permissions = set(db.execute(select(UserPermission.permission).where(UserPermission.user_id == user_id)).scalars())
    roles = sorted({role for role, _ in role_rows})
    permissions = sorted({permission for _, permission in role_rows} | direct_permissions)
    return roles, permissions


def build_user_response(db: Session, user: AppUser) -> UserResponse:
    roles, permissions = user_permissions(db, user.id)
    return UserResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status,
        roles=roles,
        permissions=permissions,
        last_login_at=user.last_login_at,
    )


def authenticate_user(db: Session, username: str, password: str) -> AppUser:
    user = db.execute(select(AppUser).where(AppUser.username == username.strip())).scalar_one_or_none()
    if user is None or user.status != "ACTIVE" or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    user.last_login_at = datetime.utcnow()
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> AppUser:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = _decode_token(authorization.split(" ", 1)[1].strip())
    user = db.get(AppUser, int(payload["sub"]))
    if user is None or user.status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User unavailable")
    return user


def require_permission(permission: str):
    def dependency(
        user: AppUser = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> AppUser:
        _, permissions = user_permissions(db, user.id)
        if "*" not in permissions and permission not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {permission}")
        return user

    return dependency


def require_super_admin(
    user: AppUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AppUser:
    roles, _ = user_permissions(db, user.id)
    if "SUPER_ADMIN" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SUPER_ADMIN role required")
    return user


def request_meta(request: Request | None) -> dict[str, str | None]:
    if request is None:
        return {"ip_address": None, "user_agent": None}
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }

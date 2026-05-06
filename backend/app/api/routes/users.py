from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import AppUser, Role, RolePermission, UserPermission, UserRole
from app.schemas.user import (
    PermissionGroup,
    PermissionOptionsResponse,
    RoleOption,
    UserCreateRequest,
    UserListItem,
    UserPermissionUpdateRequest,
    UserRoleUpdateRequest,
    UserUpdateRequest,
)
from app.services.audit import entity_summary, write_audit_log
from app.services.auth import PERMISSION_GROUPS, ROLE_TEMPLATES, build_user_response, hash_password, request_meta, require_super_admin

router = APIRouter()


def _super_admin_role(db: Session) -> Role:
    role = db.execute(select(Role).where(Role.code == "SUPER_ADMIN")).scalar_one_or_none()
    if role is None:
        raise HTTPException(status_code=500, detail="SUPER_ADMIN role is not initialized")
    return role


def _item(db: Session, user: AppUser) -> UserListItem:
    profile = build_user_response(db, user)
    direct_permissions = sorted(db.execute(select(UserPermission.permission).where(UserPermission.user_id == user.id)).scalars())
    return UserListItem(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        status=user.status,
        roles=profile.roles,
        permissions=profile.permissions,
        direct_permissions=direct_permissions,
        last_login_at=user.last_login_at,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=list[UserListItem])
def list_users(db: Session = Depends(get_db), _actor: AppUser = Depends(require_super_admin)):
    users = list(db.execute(select(AppUser).order_by(AppUser.created_at.desc())).scalars())
    return [_item(db, user) for user in users]


@router.get("/permission-options", response_model=PermissionOptionsResponse)
def permission_options(db: Session = Depends(get_db), _actor: AppUser = Depends(require_super_admin)):
    roles: list[RoleOption] = []
    for role in db.execute(select(Role).order_by(Role.code.asc())).scalars():
        permissions = list(db.execute(select(RolePermission.permission).where(RolePermission.role_id == role.id)).scalars())
        roles.append(RoleOption(code=role.code, name=role.name, description=role.description, permissions=permissions))
    known_codes = {role.code for role in roles}
    for code, template in ROLE_TEMPLATES.items():
        if code not in known_codes:
            roles.append(
                RoleOption(
                    code=code,
                    name=str(template["name"]),
                    description=str(template["description"]),
                    permissions=[str(item) for item in template["permissions"]],  # type: ignore[index]
                )
            )
    return PermissionOptionsResponse(
        roles=roles,
        groups=[PermissionGroup(**group) for group in PERMISSION_GROUPS],
    )


@router.post("", response_model=UserListItem)
def create_user(
    payload: UserCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    existing = db.execute(select(AppUser).where(AppUser.username == payload.username.strip())).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Username already exists")
    user = AppUser(
        username=payload.username.strip(),
        display_name=payload.display_name.strip() or payload.username.strip(),
        password_hash=hash_password(payload.password),
        status="ACTIVE",
    )
    db.add(user)
    db.flush()
    role = db.execute(select(Role).where(Role.code == "STUDENT")).scalar_one_or_none()
    if role is None:
        role = _super_admin_role(db)
    db.add(UserRole(user_id=user.id, role_id=role.id))
    write_audit_log(db, actor=actor, action="user.create", resource_type="app_user", resource_id=user.id, after=entity_summary(user, ["username", "display_name", "status"]), **request_meta(request))
    db.commit()
    db.refresh(user)
    return _item(db, user)


@router.patch("/{user_id}", response_model=UserListItem)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    before = entity_summary(user, ["username", "display_name", "status"])
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip() or user.username
    if payload.status is not None:
        user.status = payload.status
    if payload.password:
        user.password_hash = hash_password(payload.password)
    db.add(user)
    write_audit_log(db, actor=actor, action="user.update", resource_type="app_user", resource_id=user.id, before=before, after=entity_summary(user, ["username", "display_name", "status"]), **request_meta(request))
    db.commit()
    db.refresh(user)
    return _item(db, user)


@router.put("/{user_id}/roles", response_model=UserListItem)
def set_user_roles(
    user_id: int,
    payload: UserRoleUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    role_codes = list(dict.fromkeys(payload.roles))
    roles = list(db.execute(select(Role).where(Role.code.in_(role_codes))).scalars()) if role_codes else []
    if len(roles) != len(role_codes):
        raise HTTPException(status_code=422, detail="Unknown role code")
    before = build_user_response(db, user).roles
    db.query(UserRole).filter(UserRole.user_id == user.id).delete()
    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id))
    write_audit_log(db, actor=actor, action="user.roles.update", resource_type="app_user", resource_id=user.id, before={"roles": before}, after={"roles": role_codes}, **request_meta(request))
    db.commit()
    db.refresh(user)
    return _item(db, user)


@router.put("/{user_id}/permissions", response_model=UserListItem)
def set_user_permissions(
    user_id: int,
    payload: UserPermissionUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    actor: AppUser = Depends(require_super_admin),
):
    user = db.get(AppUser, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    allowed = {"*"}
    for group in PERMISSION_GROUPS:
        allowed.update(item["code"] for item in group["permissions"])
    unknown = [item for item in payload.permissions if item not in allowed]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown permissions: {', '.join(unknown)}")
    before = sorted(db.execute(select(UserPermission.permission).where(UserPermission.user_id == user.id)).scalars())
    db.query(UserPermission).filter(UserPermission.user_id == user.id).delete()
    for permission in list(dict.fromkeys(payload.permissions)):
        db.add(UserPermission(user_id=user.id, permission=permission))
    write_audit_log(db, actor=actor, action="user.permissions.update", resource_type="app_user", resource_id=user.id, before={"permissions": before}, after={"permissions": payload.permissions}, **request_meta(request))
    db.commit()
    db.refresh(user)
    return _item(db, user)

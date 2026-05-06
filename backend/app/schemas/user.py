from datetime import datetime

from pydantic import BaseModel, Field


class UserCreateRequest(BaseModel):
    username: str
    display_name: str
    password: str


class UserUpdateRequest(BaseModel):
    display_name: str | None = None
    password: str | None = None
    status: str | None = None


class UserListItem(BaseModel):
    id: int
    username: str
    display_name: str
    status: str
    roles: list[str]
    permissions: list[str] = Field(default_factory=list)
    direct_permissions: list[str] = Field(default_factory=list)
    last_login_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UserRoleUpdateRequest(BaseModel):
    roles: list[str] = Field(default_factory=list)


class UserPermissionUpdateRequest(BaseModel):
    permissions: list[str] = Field(default_factory=list)


class PermissionOption(BaseModel):
    code: str
    name: str


class PermissionGroup(BaseModel):
    code: str
    name: str
    permissions: list[PermissionOption]


class RoleOption(BaseModel):
    code: str
    name: str
    description: str | None = None
    permissions: list[str] = Field(default_factory=list)


class PermissionOptionsResponse(BaseModel):
    roles: list[RoleOption]
    groups: list[PermissionGroup]

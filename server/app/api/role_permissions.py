from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.users import auth_token, get_current_user, require_admin
from app.core.database import get_db
from app.services.role_permission_service import (
    ROLES,
    RolePermissionInvalidError,
    permissions_for_role,
    permissions_for_roles,
    save_role_permissions,
)
from app.services.user_role_service import user_roles

router = APIRouter(prefix="/api/v1/role-permissions", tags=["role-permissions"])


class ActionPermissionUpdate(BaseModel):
    action_key: str
    action_name: str = ""
    allowed: bool


class PermissionUpdate(BaseModel):
    page_key: str
    can_view: bool
    can_operate: bool
    actions: list[ActionPermissionUpdate] = Field(default_factory=list)


class RolePermissionUpdate(BaseModel):
    permissions: list[PermissionUpdate]


@router.get("/me")
def my_permissions(token: str = Depends(auth_token), db: Session = Depends(get_db)):
    user = get_current_user(token, db)
    roles = user_roles(user)
    return {"role": user.role, "roles": roles, "permissions": permissions_for_roles(db, roles)}


@router.get("")
def list_permissions(token: str = Depends(auth_token), db: Session = Depends(get_db)):
    require_admin(token, db)
    return {"roles": ROLES, "items": {role: permissions_for_role(db, role) for role in ROLES}}


@router.put("/{role}")
def update_permissions(role: str, data: RolePermissionUpdate, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    require_admin(token, db)
    try:
        return {"role": role, "permissions": save_role_permissions(db, role, data.permissions)}
    except RolePermissionInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

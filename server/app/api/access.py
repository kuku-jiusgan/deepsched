from collections.abc import Callable

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.users import require_authenticated_user
from app.core.database import get_db
from app.models import User
from app.services.access_control_service import (
    AccessDeniedError,
    AccessResourceNotFoundError,
    require_management_user as ensure_management_user,
    require_notification_owner as ensure_notification_owner,
    require_project_editor as ensure_project_editor,
    require_slot_operator as ensure_slot_operator,
    require_task_editor as ensure_task_editor,
)


def require_management_user(user: User = Depends(require_authenticated_user)) -> User:
    _ensure_access(lambda: ensure_management_user(user))
    return user


def require_project_editor_by_project_id(
    project_id: int,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> User:
    _ensure_access(lambda: ensure_project_editor(db, project_id, user))
    return user


def require_project_editor_by_proj_id(
    proj_id: int,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> User:
    _ensure_access(lambda: ensure_project_editor(db, proj_id, user))
    return user


def require_task_editor(
    task_id: int,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> User:
    _ensure_access(lambda: ensure_task_editor(db, task_id, user))
    return user


def require_slot_operator(
    slot_id: int,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> User:
    _ensure_access(lambda: ensure_slot_operator(db, slot_id, user))
    return user


def require_notification_owner(
    nid: int,
    user: User = Depends(require_authenticated_user),
    db: Session = Depends(get_db),
) -> User:
    _ensure_access(lambda: ensure_notification_owner(db, nid, user))
    return user


def _ensure_access(callback: Callable[[], object]) -> None:
    try:
        callback()
    except AccessResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except AccessDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

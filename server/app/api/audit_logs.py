from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.users import require_authenticated_user
from app.core.database import get_db
from app.models import Project, Task, TimeSlot, User
from app.services.audit_log_service import list_audit_logs, project_audit_detail
from app.services.role_permission_service import permissions_for_roles
from app.services.user_role_service import user_roles


router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


@router.get("")
def get_audit_logs(
    keyword: str | None = None,
    action: str | None = None,
    user_name: str | None = None,
    start_at: datetime | None = Query(default=None),
    end_at: datetime | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_authenticated_user),
):
    permission = next(
        item for item in permissions_for_roles(db, user_roles(user))
        if item["page_key"] == "/system/audit-logs"
    )
    if not permission["can_view"]:
        raise HTTPException(status_code=403, detail="当前角色没有查看操作日志的权限")
    return [
        {
            "id": item.id,
            "user_name": _operator_display_name(db, item.user_name),
            "action": item.action,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "detail": _enriched_detail(db, item),
            "created_at": item.created_at,
        }
        for item in list_audit_logs(db, keyword, action, user_name, start_at, end_at)
    ]


def _operator_display_name(db: Session, operator: str) -> str:
    if operator in {"system", "anonymous"}:
        return operator
    user = db.query(User).filter(
        (User.username == operator) | (User.display_name == operator)
    ).first()
    return user.display_name if user else operator


def _enriched_detail(db: Session, item) -> dict:
    detail = dict(item.detail or {})
    if item.action == "HTTP POST" and detail.get("path") == "/api/v1/projects":
        project = db.query(Project).filter(
            Project.created_at >= item.created_at - timedelta(seconds=1),
            Project.created_at <= item.created_at + timedelta(seconds=1),
        ).first()
        if project:
            detail.update(project_audit_detail(project))
    task_id = detail.get("task_id")
    slot = None
    if not task_id and item.target_type == "time_slot" and item.target_id:
        slot = db.query(TimeSlot).filter(TimeSlot.id == item.target_id).first()
        task_id = slot.task_id if slot else None
    if item.target_type == "time_slot" and item.target_id:
        slot = slot or db.query(TimeSlot).filter(TimeSlot.id == item.target_id).first()
        if slot:
            instrument_name = slot.instrument.name if slot.instrument else "未指定仪器"
            detail["target_display"] = (
                f"{slot.plan_start:%Y-%m-%d} · {instrument_name} · "
                f"{slot.plan_start:%H:%M}–{slot.plan_end:%H:%M}"
            )
    if task_id and not detail.get("task_display"):
        task = db.query(Task).filter(Task.id == task_id).first()
        if task:
            project = task.project
            detail["task_display"] = " · ".join(part for part in [
                project.code if project else None,
                project.name if project else None,
                task.name,
            ] if part)
    return detail

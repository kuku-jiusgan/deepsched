from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.api.users import auth_token, get_current_user
from app.models import Project, Milestone, Task, TaskDependency, TaskCapabilityRequirement, TimeSlot
from app.schemas.schemas import (
    ProjectCreate, ProjectOut, TaskCreate, TaskUpdate, TaskOut,
    MilestoneCreate, MilestoneOut, TaskCapabilityReqOut
)
from app.services.project_access_service import (
    ProjectNotVisibleError,
    get_visible_project,
    get_visible_project_dag,
    list_visible_projects,
)
from app.services.project_hours_validation_service import (
    ProjectHoursExceededError,
    validate_project_estimated_hours,
)
from app.services.project_task_rollup_service import recalculate_project_parent_hours
from app.services.project_service import ProjectCodeExistsError, create_project as create_project_service
from app.services.project_plan_change_service import (
    PlanChangeInvalidError,
    PlanChangeNotFoundError,
    delete_task_plan,
    update_project_plan,
    update_task_plan,
)
from app.services.project_status_service import calculate_project_status

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

PROJECT_INFO_WRITE_ROLES = {"系统管理员", "项目管理员", "分析所所长"}

@router.post("", response_model=ProjectOut)
def create_project(data: ProjectCreate, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    ensure_project_info_write_permission(token, db)
    try:
        return project_response(create_project_service(db, data))
    except ProjectCodeExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

@router.get("", response_model=List[ProjectOut])
def list_projects(
    token: str = Depends(auth_token),
    db: Session = Depends(get_db),
):
    return [project_response(project) for project in list_visible_projects(db, get_current_user(token, db))]

@router.get("/{proj_id}", response_model=ProjectOut)
def get_project(
    proj_id: int,
    token: str = Depends(auth_token),
    db: Session = Depends(get_db),
):
    try:
        return project_response(get_visible_project(db, proj_id, get_current_user(token, db)))
    except ProjectNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

@router.put("/{proj_id}", response_model=ProjectOut)
def update_project(proj_id: int, data: ProjectCreate, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    ensure_project_info_write_permission(token, db)
    try:
        return project_response(update_project_plan(db, proj_id, data))
    except PlanChangeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlanChangeInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

def ensure_project_info_write_permission(token: str, db: Session) -> None:
    user = get_current_user(token, db)
    if user.role not in PROJECT_INFO_WRITE_ROLES:
        raise HTTPException(status_code=403, detail="无权新建或编辑项目信息")

def project_response(project: Project) -> dict:
    data = ProjectOut.model_validate(project).model_dump()
    data["status"] = calculate_project_status(project)
    return data

@router.delete("/{proj_id}")
def delete_project(proj_id: int, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == proj_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    # Delete related records
    task_ids = [t.id for t in db.query(Task).filter(Task.project_id == proj_id).all()]
    for tid in task_ids:
        db.query(TaskDependency).filter(
            (TaskDependency.predecessor_id == tid) | (TaskDependency.task_id == tid)
        ).delete()
        db.query(TaskCapabilityRequirement).filter(TaskCapabilityRequirement.task_id == tid).delete()
        db.query(TimeSlot).filter(TimeSlot.task_id == tid).delete()
    db.query(Task).filter(Task.project_id == proj_id).delete()
    db.query(Milestone).filter(Milestone.project_id == proj_id).delete()
    db.delete(proj)
    db.commit()
    return {"detail": "已删除"}

@router.post("/{proj_id}/milestones", response_model=MilestoneOut)
def add_milestone(proj_id: int, data: MilestoneCreate, db: Session = Depends(get_db)):
    ms = Milestone(project_id=proj_id, name=data.name, due_date=data.due_date)
    db.add(ms)
    db.commit()
    db.refresh(ms)
    return ms

@router.post("/{proj_id}/tasks", response_model=TaskOut)
def add_task(proj_id: int, data: TaskCreate, db: Session = Depends(get_db)):
    task = Task(
        project_id=proj_id, name=data.name, task_type=data.task_type,
        requires_instrument=data.requires_instrument, requires_human=data.requires_human,
        est_duration_hours=data.est_duration_hours, switchover_hours=data.switchover_hours,
        assignee_id=data.assignee_id, parent_id=data.parent_id,
        allow_split=data.allow_split, allow_transfer=data.allow_transfer,
        milestone_id=data.milestone_id, priority_weight=data.priority_weight
    )
    task.instrument_ids = data.instrument_ids
    db.add(task)
    db.flush()
    # Dependencies
    for pred_id in data.predecessor_ids:
        db.add(TaskDependency(task_id=task.id, predecessor_id=pred_id))
    recalculate_project_parent_hours(db, proj_id)
    try:
        validate_project_estimated_hours(db, proj_id)
    except ProjectHoursExceededError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    db.commit()
    db.refresh(task)
    return _task_to_out(task, db)

@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    try:
        delete_task_plan(db, task_id)
        return {"detail": "已删除"}
    except PlanChangeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlanChangeInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))

@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, db: Session = Depends(get_db)):
    try:
        return _task_to_out(update_task_plan(db, task_id, data), db)
    except PlanChangeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlanChangeInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
@router.get("/{proj_id}/dag")
def get_project_dag(
    proj_id: int,
    token: str = Depends(auth_token),
    db: Session = Depends(get_db),
):
    try:
        return get_visible_project_dag(db, proj_id, get_current_user(token, db))
    except ProjectNotVisibleError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
def _task_to_out(task: Task, db: Session) -> TaskOut:
    preds = [d.predecessor_id for d in task.predecessors]
    children_out = [_task_to_out(c, db) for c in task.children] if task.children else []
    return TaskOut(
        id=task.id, project_id=task.project_id, name=task.name,
        task_type=task.task_type, requires_instrument=task.requires_instrument,
        requires_human=task.requires_human, est_duration_hours=task.est_duration_hours,
        switchover_hours=task.switchover_hours, allow_split=task.allow_split, status=task.status,
        schedule_dirty=bool(task.schedule_dirty), schedule_lock_status=task.schedule_lock_status,
        can_edit_schedule_fields=task.can_edit_schedule_fields,
        earliest_start=task.earliest_start, latest_due=task.latest_due,
        priority_weight=task.priority_weight,
        instrument_ids=task.instrument_ids or [], predecessor_ids=preds,
        assignee_id=task.assignee_id, parent_id=task.parent_id,
        assignee_name=task.assignee.display_name if task.assignee else None,
        is_external_gate=bool(task.is_external_gate), gate_status=task.gate_status,
        expected_approval_at=task.expected_approval_at, submitted_at=task.submitted_at,
        approved_at=task.approved_at,
        approved_by_name=task.approved_by_user.display_name if task.approved_by_user else None,
        approval_note=task.approval_note,
        approval_schedule_status=task.approval_schedule_status,
        children=children_out
    )


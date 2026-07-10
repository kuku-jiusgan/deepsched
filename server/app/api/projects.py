from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models import Project, Milestone, Task, TaskDependency, TaskCapabilityRequirement, TimeSlot
from app.schemas.schemas import (
    ProjectCreate, ProjectOut, TaskCreate, TaskUpdate, TaskOut,
    MilestoneCreate, MilestoneOut, TaskCapabilityReqOut
)
from app.services.project_plan_change_service import (
    PlanChangeInvalidError,
    PlanChangeNotFoundError,
    update_project_plan,
    update_task_plan,
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

@router.post("", response_model=ProjectOut)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    proj = Project(
        name=data.name, code=data.code, client_name=data.client_name,
        priority=data.priority, manager_id=data.manager_id,
        start_date=data.start_date, end_date=data.end_date
    )
    db.add(proj)
    db.commit()
    db.refresh(proj)
    return proj

@router.get("", response_model=List[ProjectOut])
def list_projects(db: Session = Depends(get_db)):
    return db.query(Project).all()

@router.get("/{proj_id}", response_model=ProjectOut)
def get_project(proj_id: int, db: Session = Depends(get_db)):
    proj = db.query(Project).filter(Project.id == proj_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    return proj

@router.put("/{proj_id}", response_model=ProjectOut)
def update_project(proj_id: int, data: ProjectCreate, db: Session = Depends(get_db)):
    try:
        return update_project_plan(db, proj_id, data)
    except PlanChangeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlanChangeInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
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
    db.commit()
    db.refresh(task)
    return _task_to_out(task, db)

@router.delete("/tasks/{task_id}")
def delete_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    # Delete dependencies first
    db.query(TaskDependency).filter(
        (TaskDependency.predecessor_id == task_id) | (TaskDependency.task_id == task_id)
    ).delete()
    db.query(TaskCapabilityRequirement).filter(TaskCapabilityRequirement.task_id == task_id).delete()
    db.query(TimeSlot).filter(TimeSlot.task_id == task_id).delete()
    db.delete(task)
    db.commit()
    return {"detail": "已删除"}

@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskUpdate, db: Session = Depends(get_db)):
    try:
        return _task_to_out(update_task_plan(db, task_id, data), db)
    except PlanChangeNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PlanChangeInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
@router.get("/{proj_id}/dag")
def get_project_dag(proj_id: int, db: Session = Depends(get_db)):
    tasks = db.query(Task).filter(Task.project_id == proj_id).all()
    nodes = []
    edges = []
    for t in tasks:
        nodes.append({"id": t.id, "name": t.name, "type": t.task_type,
                       "requires_instrument": t.requires_instrument, "status": t.status})
        for dep in t.predecessors:
            edges.append({"from": dep.predecessor_id, "to": t.id})
    return {"nodes": nodes, "edges": edges}

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
        children=children_out
    )


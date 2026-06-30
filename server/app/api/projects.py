from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models import Project, Milestone, Task, TaskDependency, TaskCapabilityRequirement
from app.schemas.schemas import (
    ProjectCreate, ProjectOut, TaskCreate, TaskOut,
    MilestoneCreate, MilestoneOut, TaskCapabilityReqOut
)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])

@router.post("", response_model=ProjectOut)
def create_project(data: ProjectCreate, db: Session = Depends(get_db)):
    proj = Project(
        name=data.name, code=data.code, client_name=data.client_name,
        priority=data.priority, sla_level=data.sla_level, profit_weight=data.profit_weight, manager=data.manager,
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
    proj = db.query(Project).filter(Project.id == proj_id).first()
    if not proj:
        raise HTTPException(status_code=404, detail="项目不存在")
    proj.name = data.name
    proj.code = data.code
    proj.client_name = data.client_name
    proj.priority = data.priority
    proj.sla_level = data.sla_level
    proj.profit_weight = data.profit_weight
    proj.manager = data.manager
    proj.start_date = data.start_date
    proj.end_date = data.end_date
    db.commit()
    db.refresh(proj)
    return proj

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
        allow_split=data.allow_split, allow_transfer=data.allow_transfer,
        milestone_id=data.milestone_id, priority_weight=data.priority_weight
    )
    db.add(task)
    db.flush()
    # Capability requirements
    for cap in data.capability_requirements:
        db.add(TaskCapabilityRequirement(task_id=task.id, tag_name=cap.tag_name, tag_value=cap.tag_value))
    # Dependencies
    for pred_id in data.predecessor_ids:
        db.add(TaskDependency(task_id=task.id, predecessor_id=pred_id))
    db.commit()
    db.refresh(task)
    return _task_to_out(task, db)

@router.put("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: int, data: TaskCreate, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    task.name = data.name
    task.task_type = data.task_type
    task.requires_instrument = data.requires_instrument
    task.requires_human = data.requires_human
    task.est_duration_hours = data.est_duration_hours
    task.switchover_hours = data.switchover_hours
    task.allow_split = data.allow_split
    task.allow_transfer = data.allow_transfer
    task.milestone_id = data.milestone_id
    task.priority_weight = data.priority_weight
    db.query(TaskCapabilityRequirement).filter(TaskCapabilityRequirement.task_id == task_id).delete()
    for cap in data.capability_requirements:
        db.add(TaskCapabilityRequirement(task_id=task_id, tag_name=cap.tag_name, tag_value=cap.tag_value))
    db.query(TaskDependency).filter(TaskDependency.task_id == task_id).delete()
    for pred_id in data.predecessor_ids:
        db.add(TaskDependency(task_id=task_id, predecessor_id=pred_id))
    db.commit()
    db.refresh(task)
    return _task_to_out(task, db)

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
    caps = [TaskCapabilityReqOut(id=c.id, tag_name=c.tag_name, tag_value=c.tag_value)
            for c in task.capability_requirements]
    preds = [d.predecessor_id for d in task.predecessors]
    return TaskOut(
        id=task.id, project_id=task.project_id, name=task.name,
        task_type=task.task_type, requires_instrument=task.requires_instrument,
        requires_human=task.requires_human, est_duration_hours=task.est_duration_hours,
        switchover_hours=task.switchover_hours, status=task.status,
        earliest_start=task.earliest_start, latest_due=task.latest_due,
        priority_weight=task.priority_weight,
        capability_requirements=caps, predecessor_ids=preds
    )

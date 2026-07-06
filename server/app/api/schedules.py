from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.config import get_settings
from app.models import TimeSlot, Task, Instrument, Project
from app.schemas.schemas import (
    TimeSlotOut, TimeSlotUpdate, TaskStatusUpdate,
    ScheduleGenerateRequest, InsertOrderRequest, InsertOrderCost,
    RescheduleRequest
)
from app.services.scheduler import SchedulerService

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])

@router.get("/timeslots", response_model=List[TimeSlotOut])
def list_timeslots(
    start_date: Optional[datetime] = Query(None),
    end_date: Optional[datetime] = Query(None),
    instrument_id: Optional[int] = Query(None),
    project_id: Optional[int] = Query(None),
    tier: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(TimeSlot)
    if start_date:
        q = q.filter(TimeSlot.plan_end > start_date)
    if end_date:
        q = q.filter(TimeSlot.plan_start < end_date)
    if instrument_id:
        q = q.filter(TimeSlot.instrument_id == instrument_id)
    if project_id:
        q = q.join(Task).filter(Task.project_id == project_id)
    if tier:
        q = q.filter(TimeSlot.tier == tier)
    slots = q.order_by(TimeSlot.plan_start).all()
    return [_enrich_slot(s, db) for s in slots]

@router.put("/timeslots/{slot_id}", response_model=TimeSlotOut)
def update_timeslot(slot_id: int, data: TimeSlotUpdate, db: Session = Depends(get_db)):
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="时间槽不存在")
    if slot.tier == "frozen":
        raise HTTPException(status_code=400, detail="冻结期时间槽不可手动调整")
    if data.plan_start is not None:
        slot.plan_start = data.plan_start
    if data.plan_end is not None:
        slot.plan_end = data.plan_end
    if data.instrument_id is not None:
        slot.instrument_id = data.instrument_id
    if data.tier is not None:
        slot.tier = data.tier
    db.commit()
    db.refresh(slot)
    return _enrich_slot(slot, db)

@router.post("/timeslots/{slot_id}/start")
def start_task(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="时间槽不存在")
    task = db.query(Task).filter(Task.id == slot.task_id).first()
    task.status = "running"
    # Update ALL time slots for this task (handles night-window chunking)
    for s in db.query(TimeSlot).filter(TimeSlot.task_id == slot.task_id, TimeSlot.status == "scheduled").all():
        s.status = "running"
        if s.id == slot_id:
            s.actual_start = datetime.now()
    db.commit()
    return {"status": "ok"}

@router.post("/timeslots/{slot_id}/complete")
def complete_task(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="时间槽不存在")
    task = db.query(Task).filter(Task.id == slot.task_id).first()
    task.status = "done"
    # Update ALL time slots for this task (handles night-window chunking)
    for s in db.query(TimeSlot).filter(TimeSlot.task_id == slot.task_id, TimeSlot.status.in_(["scheduled", "running"])).all():
        s.status = "completed"
        if s.id == slot_id:
            s.actual_end = datetime.now()
    db.commit()
    return {"status": "ok"}

@router.post("/timeslots/{slot_id}/interrupt")
def interrupt_task(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="时间槽不存在")
    slot.status = "interrupted"
    slot.actual_end = datetime.now()
    task = db.query(Task).filter(Task.id == slot.task_id).first()
    task.status = "blocked"
    db.commit()
    return {"status": "ok"}

@router.post("/generate")
def generate_schedule(data: ScheduleGenerateRequest, db: Session = Depends(get_db)):
    scheduler = SchedulerService(db)
    result = scheduler.generate(data.project_ids)
    return result

@router.post("/reschedule")
def reschedule(data: RescheduleRequest, db: Session = Depends(get_db)):
    scheduler = SchedulerService(db)
    result = scheduler.reschedule(data)
    return result

@router.post("/insert-order", response_model=InsertOrderCost)
def calculate_insert_cost(data: InsertOrderRequest, db: Session = Depends(get_db)):
    scheduler = SchedulerService(db)
    return scheduler.calculate_insert_cost(data)

@router.post("/insert-order/confirm")
def confirm_insert(data: InsertOrderRequest, db: Session = Depends(get_db)):
    scheduler = SchedulerService(db)
    return scheduler.execute_insert(data)

@router.post("/daily-roll")
def daily_roll(db: Session = Depends(get_db)):
    now = datetime.now()
    settings = get_settings()
    frozen_boundary = now + timedelta(days=settings.FROZEN_DAYS)
    confirmed_boundary = now + timedelta(days=settings.CONFIRMED_DAYS)

    db.query(TimeSlot).filter(
        TimeSlot.tier == "confirmed",
        TimeSlot.plan_start <= frozen_boundary
    ).update({"tier": "frozen"}, synchronize_session=False)

    db.query(TimeSlot).filter(
        TimeSlot.tier == "forecast",
        TimeSlot.plan_start <= confirmed_boundary
    ).update({"tier": "confirmed"}, synchronize_session=False)

    db.commit()
    return {"status": "ok", "rolled_at": now.isoformat()}


@router.get("/my-tasks")
def my_tasks(token: str, db: Session = Depends(get_db)):
    """Return tasks assigned to the current user, with time slot info if scheduled."""
    from app.api.users import get_current_user
    user = get_current_user(token, db)

    # Auto-delay: mark overdue tasks as blocked (no reschedule triggered)
    now = datetime.now()
    overdue_tasks = db.query(Task).filter(
        Task.assignee_id == user.id,
        Task.status.in_(["scheduled", "running"]),
    ).all()
    for t in overdue_tasks:
        slot = db.query(TimeSlot).filter(
            TimeSlot.task_id == t.id,
            TimeSlot.status.in_(["scheduled", "running"]),
        ).first()
        if slot and slot.plan_end and slot.plan_end < now:
            t.status = "blocked"
            if slot:
                slot.status = "blocked"
    db.commit()

    # Query tasks assigned to this user
    tasks = db.query(Task).filter(
        Task.assignee_id == user.id,
        Task.status.in_(["pending", "running", "blocked", "scheduled", "done", "interrupted"])
    ).order_by(Task.id).all()
    
    result = []
    for task in tasks:
        proj = db.query(Project).filter(Project.id == task.project_id).first()
        # Find a time slot if this task has been scheduled
        slot = db.query(TimeSlot).filter(
            TimeSlot.task_id == task.id,
            TimeSlot.status.in_(["scheduled", "running", "interrupted", "blocked", "completed"])
        ).first()
        
        inst = db.query(Instrument).filter(Instrument.id == slot.instrument_id).first() if slot else None
        
        result.append({
            "slot_id": slot.id if slot else 0,
            "task_id": task.id,
            "task_name": task.name,
            "task_type": task.task_type,
            "project_id": proj.id if proj else None,
            "project_name": proj.name if proj else None,
            "project_code": proj.code if proj else None,
            "instrument_id": slot.instrument_id if slot else 0,
            "instrument_name": inst.name if inst else None,
            "instrument_code": inst.code if inst else None,
            "plan_start": slot.plan_start.isoformat() if slot and slot.plan_start else None,
            "plan_end": slot.plan_end.isoformat() if slot and slot.plan_end else None,
            "actual_start": slot.actual_start.isoformat() if slot and slot.actual_start else None,
            "status": task.status,
            "tier": slot.tier if slot else "unscheduled",
            "est_duration_hours": task.est_duration_hours,
        })
    return result

def _enrich_slot(slot: TimeSlot, db: Session) -> TimeSlotOut:
    task = db.query(Task).filter(Task.id == slot.task_id).first()
    inst = db.query(Instrument).filter(Instrument.id == slot.instrument_id).first()
    proj = db.query(Project).filter(Project.id == task.project_id).first() if task else None
    return TimeSlotOut(
        id=slot.id, task_id=slot.task_id, instrument_id=slot.instrument_id,
        plan_start=slot.plan_start, plan_end=slot.plan_end,
        actual_start=slot.actual_start, actual_end=slot.actual_end,
        tier=slot.tier, status=slot.status,
        task_name=task.name if task else None,
        task_type=task.task_type if task else None,
        project_name=proj.name if proj else None,
        instrument_name=inst.name if inst else None,
        assignee_name=task.assignee.display_name if task and task.assignee else None,
        project_id=task.project_id if task else None
    )


from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import json
from datetime import datetime, timedelta
from app.core.database import get_db
from app.core.config import get_settings
from app.models import TimeSlot, Task, Instrument, Project, AuditLog
from app.schemas.schemas import (
    TimeSlotOut, TimeSlotUpdate, TaskStatusUpdate,
    ScheduleGenerateRequest, InsertOrderRequest, InsertOrderPreview, InsertOrderResult,
    RescheduleRequest, TaskDelayRequest, TaskDelayResponse,
    NightRunRequest, TaskCompleteRequest, TaskCompleteResponse
)
from app.services.scheduler import SchedulerService
from app.services.schedule_delay_service import (
    ScheduleDelayInvalidError,
    ScheduleDelayNotFoundError,
    report_task_delay,
)
from app.services.schedule_completion_service import complete_task_and_shift
from app.services.instrument_status_service import mark_instrument_running, refresh_instrument_status
from app.services.schedule_insert_service import (
    ScheduleInsertInvalidError,
    ScheduleInsertNotFoundError,
    confirm_insert as confirm_insert_service,
    preview_insert,
)
from app.services.schedule_night_run_service import (
    ScheduleNightRunInvalidError,
    ScheduleNightRunNotFoundError,
    record_night_run,
)
from app.services.schedule_reschedule_service import reschedule as reschedule_service
from app.api.users import auth_token

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
    started_at = datetime.now()
    for running_slot in _continuous_running_slots(db, slot):
        running_slot.status = "running"
        if running_slot.id == slot.id:
            running_slot.actual_start = started_at
        mark_instrument_running(db, running_slot.instrument_id)
    db.commit()
    return {"status": "ok"}

@router.post("/timeslots/{slot_id}/complete", response_model=TaskCompleteResponse)
def complete_task(
    slot_id: int,
    data: TaskCompleteRequest = TaskCompleteRequest(),
    db: Session = Depends(get_db),
):
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="时间槽不存在")
    return complete_task_and_shift(
        db,
        slot.task_id,
        completed_slot_id=slot.id,
        release_instrument=data.release_instrument,
    )

@router.post("/timeslots/{slot_id}/interrupt")
def interrupt_task(slot_id: int, db: Session = Depends(get_db)):
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise HTTPException(status_code=404, detail="时间槽不存在")
    slot.status = "interrupted"
    slot.actual_end = datetime.now()
    task = db.query(Task).filter(Task.id == slot.task_id).first()
    task.status = "blocked"
    refresh_instrument_status(db, slot.instrument_id)
    db.commit()
    return {"status": "ok"}

@router.post("/timeslots/{slot_id}/delay", response_model=TaskDelayResponse)
def delay_task(slot_id: int, data: TaskDelayRequest, db: Session = Depends(get_db)):
    try:
        return report_task_delay(db, slot_id, data.delay_hours, data.reason)
    except ScheduleDelayNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScheduleDelayInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/timeslots/{slot_id}/night-run", response_model=TimeSlotOut)
def night_run(slot_id: int, data: NightRunRequest, db: Session = Depends(get_db)):
    try:
        slot = record_night_run(db, slot_id, data.duration_hours, data.earliest_start, data.latest_end)
        return _enrich_slot(slot, db)
    except ScheduleNightRunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScheduleNightRunInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/generate")
def generate_schedule(data: ScheduleGenerateRequest, db: Session = Depends(get_db)):
    scheduler = SchedulerService(db)
    result = scheduler.generate(data.project_ids, mode=data.mode)
    return result

@router.post("/reschedule")
def reschedule(data: RescheduleRequest, db: Session = Depends(get_db)):
    return reschedule_service(db, data)

@router.post("/insert-order", response_model=InsertOrderPreview)
def calculate_insert_cost(data: InsertOrderRequest, db: Session = Depends(get_db)):
    try:
        return preview_insert(db, data)
    except ScheduleInsertNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScheduleInsertInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

@router.post("/insert-order/confirm", response_model=InsertOrderResult)
def confirm_insert(data: InsertOrderRequest, db: Session = Depends(get_db)):
    try:
        return confirm_insert_service(db, data)
    except ScheduleInsertNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ScheduleInsertInvalidError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
def my_tasks(token: str = Depends(auth_token), db: Session = Depends(get_db)):
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

    # Query leaf tasks only: exclude tasks that have children (parent nodes)
    from sqlalchemy import not_
    parent_ids = db.query(Task.parent_id).filter(Task.parent_id != None).subquery()

    tasks = db.query(Task).filter(
        Task.assignee_id == user.id,
        Task.status.in_(["pending", "running", "blocked", "scheduled", "done", "interrupted"]),
        not_(Task.id.in_(parent_ids)),
    ).order_by(Task.id).all()
    
    result = []
    for task in tasks:
        proj = db.query(Project).filter(Project.id == task.project_id).first()
        # Find all scheduled segments for the task. The workspace table shows
        # the full task window, while actions still use the current segment.
        task_slots = db.query(TimeSlot).filter(
            TimeSlot.task_id == task.id,
            TimeSlot.status.in_(["scheduled", "running", "interrupted", "blocked", "completed"])
        ).order_by(TimeSlot.plan_start, TimeSlot.id).all()
        slot = _select_workspace_slot(task_slots, now)
        task_plan_start = min((s.plan_start for s in task_slots if s.plan_start), default=None)
        task_plan_end = max((s.plan_end for s in task_slots if s.plan_end), default=None)
        
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
            "task_plan_start": task_plan_start.isoformat() if task_plan_start else None,
            "task_plan_end": task_plan_end.isoformat() if task_plan_end else None,
            "actual_start": slot.actual_start.isoformat() if slot and slot.actual_start else None,
            "actual_end": slot.actual_end.isoformat() if slot and slot.actual_end else None,
            "status": task.status,
            "tier": slot.tier if slot else "unscheduled",
            "est_duration_hours": task.est_duration_hours,
            **(
                _latest_delay_fields(task.id, db, slot)
                if slot and _should_include_delay_fields(slot)
                else _empty_delay_fields()
            ),
        })
    return result

RUNNING_CONTINUATION_STATUSES = {"scheduled", "running"}

def _continuous_running_slots(db: Session, start_slot: TimeSlot) -> list[TimeSlot]:
    return (
        db.query(TimeSlot)
        .filter(
            TimeSlot.task_id == start_slot.task_id,
            TimeSlot.plan_end >= start_slot.plan_start,
            TimeSlot.status.in_(RUNNING_CONTINUATION_STATUSES),
        )
        .order_by(TimeSlot.plan_start, TimeSlot.id)
        .all()
    )

def _select_workspace_slot(slots: list[TimeSlot], now: datetime) -> Optional[TimeSlot]:
    running_slot = next((slot for slot in slots if slot.status == "running"), None)
    if running_slot:
        return running_slot

    active_slot = next(
        (
            slot for slot in slots
            if slot.status in {"scheduled", "blocked", "interrupted"}
            and slot.plan_end
            and slot.plan_end >= now
        ),
        None,
    )
    if active_slot:
        return active_slot

    open_slot = next((slot for slot in slots if slot.status != "completed"), None)
    if open_slot:
        return open_slot

    return slots[-1] if slots else None

def _empty_delay_fields() -> dict:
    return {
        "delay_hours": None,
        "delay_reason": None,
        "delay_reported_at": None,
    }

def _should_include_delay_fields(slot: TimeSlot) -> bool:
    if slot.status in {"blocked", "interrupted"}:
        return True
    return slot.status == "running" and slot.actual_start is not None

def _enrich_slot(slot: TimeSlot, db: Session) -> TimeSlotOut:
    task = db.query(Task).filter(Task.id == slot.task_id).first()
    inst = db.query(Instrument).filter(Instrument.id == slot.instrument_id).first()
    proj = db.query(Project).filter(Project.id == task.project_id).first() if task else None
    delay_fields = (
        _latest_delay_fields(task.id, db, slot)
        if task and _should_include_delay_fields(slot)
        else _empty_delay_fields()
    )
    return TimeSlotOut(
        id=slot.id, schedule_run_id=slot.schedule_run_id,
        task_id=slot.task_id, instrument_id=slot.instrument_id,
        plan_start=slot.plan_start, plan_end=slot.plan_end,
        actual_start=slot.actual_start, actual_end=slot.actual_end,
        tier=slot.tier, status=slot.status,
        task_name=task.name if task else None,
        task_type=task.task_type if task else None,
        project_code=proj.code if proj else None,
        project_name=proj.name if proj else None,
        instrument_name=inst.name if inst else None,
        instrument_code=inst.code if inst else None,
        assignee_name=task.assignee.display_name if task and task.assignee else None,
        project_id=task.project_id if task else None,
        **delay_fields,
    )

def _latest_delay_fields(task_id: int, db: Session, slot: TimeSlot) -> dict:
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.action == "task_delay_reported")
        .order_by(AuditLog.created_at.desc())
        .limit(50)
        .all()
    )
    for log in logs:
        if log.target_id != slot.id:
            continue
        detail = _audit_detail_dict(log.detail)
        if detail.get("schedule_run_id") != slot.schedule_run_id:
            continue
        if detail.get("task_id") == task_id:
            return {
                "delay_hours": detail.get("delay_hours"),
                "delay_reason": detail.get("reason"),
                "delay_reported_at": log.created_at,
            }
    return _empty_delay_fields()

def _audit_detail_dict(detail) -> dict:
    if isinstance(detail, dict):
        return detail
    if isinstance(detail, str):
        try:
            parsed = json.loads(detail)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


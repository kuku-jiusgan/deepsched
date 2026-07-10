from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models import Instrument, TimeSlot, Task, Project, InstrumentFault
from app.schemas.schemas import DashboardData, UtilizationStats

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])


@router.get("/dashboard", response_model=DashboardData)
def dashboard(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    window_start, window_end = _stats_window(start_date, end_date, settings)

    available_instruments = (
        db.query(Instrument)
        .filter(Instrument.availability_status == "available")
        .all()
    )
    available_instrument_ids = [instrument.id for instrument in available_instruments]
    total_inst = len(available_instruments)
    active_inst = db.query(Instrument).filter(Instrument.availability_status == "available").count()
    project_window_filter = (
        or_(Project.start_date.is_(None), Project.start_date < window_end),
        or_(Project.end_date.is_(None), Project.end_date > window_start),
    )
    total_proj = db.query(Project).filter(*project_window_filter).count()
    active_proj = db.query(Project).filter(Project.status == "active", *project_window_filter).count()
    delayed = (
        db.query(Task.id)
        .join(TimeSlot, TimeSlot.task_id == Task.id)
        .filter(
            Task.status == "blocked",
            TimeSlot.plan_end > window_start,
            TimeSlot.plan_start < window_end,
        )
        .distinct()
        .count()
    )

    slots = db.query(TimeSlot).filter(
        TimeSlot.plan_end > window_start,
        TimeSlot.plan_start < window_end,
        TimeSlot.status.in_(["completed", "running"]),
    ).all()
    if available_instrument_ids:
        slots = [slot for slot in slots if slot.instrument_id in available_instrument_ids]
    else:
        slots = []
    total_hours = sum(_actual_run_hours(slot, window_start, window_end) for slot in slots)
    total_available = sum(
        _available_hours(db, instrument.id, window_start, window_end)
        for instrument in available_instruments
    )
    avg_util = round(total_hours / total_available * settings.PERCENT_SCALE, 1) if total_available > 0 else 0

    return DashboardData(
        total_instruments=total_inst,
        active_instruments=active_inst,
        total_projects=total_proj,
        active_projects=active_proj,
        avg_utilization=avg_util,
        delayed_tasks=delayed,
        buffer_warnings=[],
        milestone_risks=[],
    )


@router.get("/utilization", response_model=List[UtilizationStats])
def utilization(
    start_date: datetime | None = Query(None),
    end_date: datetime | None = Query(None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    instruments = db.query(Instrument).filter(Instrument.availability_status == "available").all()
    window_start, window_end = _stats_window(start_date, end_date, settings)
    window_hours = (window_end - window_start).total_seconds() / 3600
    result = []
    for inst in instruments:
        slots = db.query(TimeSlot).filter(
            TimeSlot.instrument_id == inst.id,
            TimeSlot.plan_end > window_start,
            TimeSlot.plan_start < window_end,
        ).all()
        scheduled = sum(_overlap_hours(slot.plan_start, slot.plan_end, window_start, window_end) for slot in slots)
        actual = sum(_actual_run_hours(slot, window_start, window_end) for slot in slots)
        available = _available_hours(db, inst.id, window_start, window_end)
        expected_rate = round(available / window_hours * settings.PERCENT_SCALE, 1) if window_hours > 0 else 0
        actual_rate = round(actual / available * settings.PERCENT_SCALE, 1) if available > 0 else 0
        result.append(UtilizationStats(
            instrument_id=inst.id,
            instrument_name=inst.name,
            instrument_code=inst.code,
            total_available_hours=available,
            scheduled_hours=round(scheduled, 1),
            actual_run_hours=round(actual, 1),
            expected_utilization_rate=expected_rate,
            actual_utilization_rate=actual_rate,
            utilization_rate=actual_rate,
            buffer_consumed_rate=0,
        ))
    return result


def _stats_window(start_date: datetime | None, end_date: datetime | None, settings) -> tuple[datetime, datetime]:
    now = datetime.now()
    window_start = start_date or (now - timedelta(days=settings.STATS_WINDOW_DAYS))
    window_end = end_date or now
    if window_end.date() > now.date():
        raise HTTPException(status_code=400, detail="筛选结束日期不能晚于当前日期")
    if window_end > now:
        window_end = now
    if window_start >= window_end:
        raise HTTPException(status_code=400, detail="开始时间必须早于结束时间")
    return window_start, window_end


def _available_hours(db: Session, instrument_id: int, window_start: datetime, window_end: datetime) -> float:
    total_hours = (window_end - window_start).total_seconds() / 3600
    faults = db.query(InstrumentFault).filter(
        InstrumentFault.instrument_id == instrument_id,
        InstrumentFault.reported_at < window_end,
    ).all()
    fault_hours = sum(_fault_overlap_hours(fault, window_start, window_end) for fault in faults)
    return max(0, round(total_hours - fault_hours, 1))


def _fault_overlap_hours(fault: InstrumentFault, window_start: datetime, window_end: datetime) -> float:
    fault_end = fault.resolved_at if fault.resolved_at else window_end
    if fault_end > window_end:
        fault_end = window_end
    return _overlap_hours(fault.reported_at, fault_end, window_start, window_end)


def _actual_run_hours(slot: TimeSlot, window_start: datetime, window_end: datetime) -> float:
    if slot.status not in ["completed", "running"] or not slot.actual_start:
        return 0
    end_time = slot.actual_end if slot.actual_end else window_end
    return _overlap_hours(slot.actual_start, end_time, window_start, window_end)


def _overlap_hours(start_time: datetime, end_time: datetime, window_start: datetime, window_end: datetime) -> float:
    start = max(start_time, window_start)
    end = min(end_time, window_end)
    if end <= start:
        return 0
    return (end - start).total_seconds() / 3600


@router.get("/lab-status")
def lab_status(db: Session = Depends(get_db)):
    instruments = db.query(Instrument).filter(Instrument.availability_status == "available").all()
    now = datetime.now()
    result = []
    for inst in instruments:
        running = db.query(TimeSlot).filter(
            TimeSlot.instrument_id == inst.id,
            TimeSlot.status == "running",
        ).first()

        current_task = None
        current_project = None
        progress = None
        if running:
            task = db.query(Task).filter(Task.id == running.task_id).first()
            if task:
                proj = db.query(Project).filter(Project.id == task.project_id).first()
                current_task = task.name
                current_project = proj.name if proj else None
                if running.actual_start and running.plan_end:
                    elapsed = (now - running.actual_start).total_seconds()
                    total = (running.plan_end - running.plan_start).total_seconds()
                    if total > 0:
                        progress = min(round(elapsed / total * 100, 1), 100)

        upcoming = db.query(TimeSlot).filter(
            TimeSlot.instrument_id == inst.id,
            TimeSlot.status == "scheduled",
            TimeSlot.plan_start > now,
        ).order_by(TimeSlot.plan_start).first()
        next_task = None
        next_start = None
        if upcoming:
            task = db.query(Task).filter(Task.id == upcoming.task_id).first()
            if task:
                next_task = task.name
                next_start = upcoming.plan_start.isoformat()

        result.append({
            "id": inst.id,
            "code": inst.code,
            "name": inst.name,
            "group": inst.instrument_group,
            "location": inst.location,
            "status": inst.status,
            "buffer_rate": inst.buffer_rate,
            "label_x": inst.label_x or 0,
            "label_y": inst.label_y or 0,
            "current_task": current_task,
            "current_project": current_project,
            "progress": progress,
            "next_task": next_task,
            "next_start": next_start,
            "running_slot_id": running.id if running else None,
            "running_start": running.actual_start.isoformat() if running and running.actual_start else None,
        })
    return result

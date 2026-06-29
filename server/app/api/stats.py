from fastapi import APIRouter, Depends
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
from app.core.database import get_db
from app.models import Instrument, TimeSlot, Task, Project, Notification
from app.schemas.schemas import UtilizationStats, DashboardData

router = APIRouter(prefix="/api/v1/stats", tags=["stats"])

@router.get("/dashboard", response_model=DashboardData)
def dashboard(db: Session = Depends(get_db)):
    total_inst = db.query(Instrument).count()
    active_inst = db.query(Instrument).filter(Instrument.status == "active").count()
    total_proj = db.query(Project).count()
    active_proj = db.query(Project).filter(Project.status == "active").count()
    delayed = db.query(Task).filter(Task.status == "blocked").count()

    # 骞冲潎鍒╃敤鐜?
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    slots = db.query(TimeSlot).filter(
        TimeSlot.plan_start >= week_ago,
        TimeSlot.status.in_(["completed", "running"])
    ).all()
    total_hours = sum(((s.actual_end or s.plan_end) - (s.actual_start or s.plan_start)).total_seconds() / 3600 for s in slots)
    total_available = active_inst * 7 * 24
    avg_util = round(total_hours / total_available * 100, 1) if total_available > 0 else 0

    return DashboardData(
        total_instruments=total_inst,
        active_instruments=active_inst,
        total_projects=total_proj,
        active_projects=active_proj,
        avg_utilization=avg_util,
        delayed_tasks=delayed,
        buffer_warnings=[],
        milestone_risks=[]
    )

@router.get("/utilization", response_model=List[UtilizationStats])
def utilization(db: Session = Depends(get_db)):
    instruments = db.query(Instrument).all()
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    result = []
    for inst in instruments:
        slots = db.query(TimeSlot).filter(
            TimeSlot.instrument_id == inst.id,
            TimeSlot.plan_start >= week_ago
        ).all()
        scheduled = sum(((s.plan_end - s.plan_start).total_seconds() / 3600) for s in slots)
        actual = sum((((s.actual_end or s.plan_end) - (s.actual_start or s.plan_start)).total_seconds() / 3600) for s in slots if s.status in ["completed", "running"])
        available = 7 * 24
        rate = round(actual / available * 100, 1) if available > 0 else 0
        result.append(UtilizationStats(
            instrument_id=inst.id,
            instrument_name=inst.name,
            total_available_hours=available,
            scheduled_hours=round(scheduled, 1),
            actual_run_hours=round(actual, 1),
            utilization_rate=rate,
            buffer_consumed_rate=0
        ))
    return result

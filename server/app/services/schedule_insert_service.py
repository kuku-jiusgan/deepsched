from datetime import datetime

from sqlalchemy.orm import Session

from app.models import Task, TimeSlot
from app.schemas.schemas import InsertOrderCost, InsertOrderRequest


def calculate_insert_cost(db: Session, data: InsertOrderRequest) -> InsertOrderCost:
    tasks = db.query(Task).filter(Task.id.in_(data.task_ids)).all()
    if not tasks:
        return InsertOrderCost()

    total_hours = sum(task.est_duration_hours or 4 for task in tasks)
    affected_slots = (
        db.query(TimeSlot)
        .filter(
            TimeSlot.tier == "confirmed",
            TimeSlot.status == "scheduled",
            TimeSlot.plan_start >= datetime.now(),
        )
        .order_by(TimeSlot.plan_start)
        .limit(20)
        .all()
    )

    displaced = []
    affected_projects = set()
    total_delay = 0.0

    for slot in affected_slots:
        delay = total_hours * 0.5
        total_delay += delay
        displaced.append({
            "task_id": slot.task_id,
            "task_name": slot.task.name if slot.task else "",
            "project_name": slot.task.project.name if slot.task and slot.task.project else "",
            "original_start": slot.plan_start.isoformat() if slot.plan_start else "",
            "delay_hours": round(delay, 1),
        })
        if slot.task and slot.task.project:
            affected_projects.add(slot.task.project.name)

    return InsertOrderCost(
        displaced_tasks=displaced,
        affected_projects=[{"name": name} for name in affected_projects],
        milestone_violations=[],
        total_delay_hours=round(total_delay, 1),
    )

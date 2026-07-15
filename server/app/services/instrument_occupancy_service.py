from __future__ import annotations

from datetime import datetime

from app.models import Task, TimeSlot


ACTIVE_SLOT_STATUSES = {"scheduled", "running", "blocked", "interrupted"}
COMPLETED_TASK_STATUSES = {"done", "completed"}


def current_occupying_slot(
    db,
    instrument_id: int,
    now: datetime,
    excluded_task_id: int | None = None,
) -> TimeSlot | None:
    actual_query = (
        db.query(TimeSlot)
        .join(Task, Task.id == TimeSlot.task_id)
        .filter(
            TimeSlot.instrument_id == instrument_id,
            TimeSlot.actual_start.isnot(None),
            TimeSlot.actual_end.is_(None),
            TimeSlot.status.in_(ACTIVE_SLOT_STATUSES),
            ~Task.status.in_(COMPLETED_TASK_STATUSES),
        )
    )
    if excluded_task_id is not None:
        actual_query = actual_query.filter(Task.id != excluded_task_id)
    actual_slot = actual_query.order_by(
        TimeSlot.actual_start.desc(), TimeSlot.id.desc()
    ).first()
    if actual_slot:
        return actual_slot

    planned_query = (
        db.query(TimeSlot)
        .join(Task, Task.id == TimeSlot.task_id)
        .filter(
            TimeSlot.instrument_id == instrument_id,
            TimeSlot.plan_start <= now,
            TimeSlot.status.in_(ACTIVE_SLOT_STATUSES),
            ~Task.status.in_(COMPLETED_TASK_STATUSES),
        )
    )
    if excluded_task_id is not None:
        planned_query = planned_query.filter(Task.id != excluded_task_id)
    return planned_query.order_by(TimeSlot.plan_start, TimeSlot.id).first()

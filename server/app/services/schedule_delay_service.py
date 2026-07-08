from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable, Set

from app.models import AuditLog, Task, TimeSlot


class ScheduleDelayNotFoundError(Exception):
    pass


class ScheduleDelayInvalidError(Exception):
    pass


ACTIVE_SLOT_STATUSES = ["scheduled", "running", "blocked", "interrupted"]
ACTIVE_TASK_STATUSES = ["pending", "scheduled", "running", "blocked", "interrupted"]


def report_task_delay(db, slot_id: int, delay_hours: float, reason: str) -> dict:
    clean_reason = reason.strip()
    if delay_hours <= 0:
        raise ScheduleDelayInvalidError("延期时长必须大于 0")
    if not clean_reason:
        raise ScheduleDelayInvalidError("请填写异常原因")

    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise ScheduleDelayNotFoundError("时间槽不存在")

    task = db.query(Task).filter(Task.id == slot.task_id).first()
    if not task:
        raise ScheduleDelayNotFoundError("任务不存在")

    delay = timedelta(hours=delay_hours)
    cutoff = slot.plan_end
    affected_slot_ids = _affected_slot_ids(db, task, slot, cutoff)

    slot.plan_end = slot.plan_end + delay
    if task.status != "running" and slot.status != "running":
        slot.status = "blocked"
        task.status = "blocked"

    shifted_count = _shift_slots(db, affected_slot_ids - {slot.id}, delay)
    _write_audit_log(db, task.id, slot.id, delay_hours, clean_reason, shifted_count)

    db.commit()
    return {
        "status": "ok",
        "task_id": task.id,
        "slot_id": slot.id,
        "delay_hours": delay_hours,
        "shifted_slots": shifted_count,
        "affected_tasks": _affected_task_count(db, affected_slot_ids),
        "reason": clean_reason,
    }


def _affected_slot_ids(db, task: Task, slot: TimeSlot, cutoff: datetime) -> Set[int]:
    slot_ids = {slot.id}
    slot_ids.update(_ids(_same_project_slots(db, task, cutoff)))
    if slot.instrument_id:
        slot_ids.update(_ids(_same_instrument_slots(db, slot, cutoff)))
    return slot_ids


def _same_project_slots(db, task: Task, cutoff: datetime) -> Iterable[TimeSlot]:
    task_ids = db.query(Task.id).filter(
        Task.project_id == task.project_id,
        Task.status.in_(ACTIVE_TASK_STATUSES),
    )
    return db.query(TimeSlot).filter(
        TimeSlot.task_id.in_(task_ids),
        TimeSlot.status.in_(ACTIVE_SLOT_STATUSES),
        TimeSlot.plan_start >= cutoff,
    ).all()


def _same_instrument_slots(db, slot: TimeSlot, cutoff: datetime) -> Iterable[TimeSlot]:
    return db.query(TimeSlot).filter(
        TimeSlot.instrument_id == slot.instrument_id,
        TimeSlot.status.in_(ACTIVE_SLOT_STATUSES),
        TimeSlot.plan_start >= cutoff,
    ).all()


def _shift_slots(db, slot_ids: Set[int], delay: timedelta) -> int:
    shifted = 0
    for future_slot in db.query(TimeSlot).filter(TimeSlot.id.in_(slot_ids)).all():
        future_slot.plan_start = future_slot.plan_start + delay
        future_slot.plan_end = future_slot.plan_end + delay
        shifted += 1
    return shifted


def _affected_task_count(db, slot_ids: Set[int]) -> int:
    if not slot_ids:
        return 0
    rows = db.query(TimeSlot.task_id).filter(TimeSlot.id.in_(slot_ids)).distinct().all()
    return len(rows)


def _write_audit_log(
    db,
    task_id: int,
    slot_id: int,
    delay_hours: float,
    reason: str,
    shifted_count: int,
) -> None:
    db.add(AuditLog(
        user_name="system",
        action="task_delay_reported",
        target_type="time_slot",
        target_id=slot_id,
        detail={
            "task_id": task_id,
            "delay_hours": delay_hours,
            "reason": reason,
            "shifted_slots": shifted_count,
        },
    ))


def _ids(slots: Iterable[TimeSlot]) -> Set[int]:
    return {slot.id for slot in slots}

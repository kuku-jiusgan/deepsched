from __future__ import annotations

from datetime import datetime

from app.models import Task, TimeSlot
from app.services.instrument_status_service import mark_instrument_running


COMPLETED_TASK_STATUSES = {"done", "completed"}
STARTABLE_SLOT_STATUSES = {"scheduled", "blocked"}
RUNNING_CONTINUATION_STATUSES = {"scheduled", "running", "blocked"}


class TaskExecutionNotFoundError(Exception):
    pass


class TaskExecutionInvalidError(Exception):
    pass


def start_task_execution(db, slot_id: int) -> dict[str, str]:
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise TaskExecutionNotFoundError("时间槽不存在")
    task = db.query(Task).filter(Task.id == slot.task_id).first()
    if not task:
        raise TaskExecutionNotFoundError("任务不存在")
    _ensure_can_start(task, slot)

    started_at = datetime.now()
    task.status = "running"
    if task.project:
        task.project.status = "active"
    for running_slot in _continuous_slots(db, slot):
        running_slot.status = "running"
        if running_slot.id == slot.id:
            running_slot.actual_start = started_at
        mark_instrument_running(db, running_slot.instrument_id)
    db.commit()
    return {"status": "ok"}


def ensure_predecessors_completed(task: Task) -> None:
    incomplete = [
        dependency.predecessor.name
        for dependency in task.predecessors
        if dependency.predecessor.status not in COMPLETED_TASK_STATUSES
    ]
    if incomplete:
        names = "、".join(incomplete[:3])
        raise TaskExecutionInvalidError(f"前置任务【{names}】尚未完成，不能操作【{task.name}】")


def _ensure_can_start(task: Task, slot: TimeSlot) -> None:
    if task.status in COMPLETED_TASK_STATUSES or slot.status == "completed":
        raise TaskExecutionInvalidError("任务已经完成，不能重复开始")
    if task.status == "running" or any(
        task_slot.actual_start is not None and task_slot.actual_end is None
        for task_slot in task.time_slots
    ):
        raise TaskExecutionInvalidError("任务已经开始，不能重复操作")
    if slot.status not in STARTABLE_SLOT_STATUSES:
        raise TaskExecutionInvalidError("当前任务状态不能开始")
    if slot.plan_start and datetime.now() < slot.plan_start:
        raise TaskExecutionInvalidError(
            f"任务计划于 {slot.plan_start:%Y-%m-%d %H:%M} 开始，当前不能提前启动"
        )
    ensure_predecessors_completed(task)


def _continuous_slots(db, start_slot: TimeSlot) -> list[TimeSlot]:
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

from __future__ import annotations

from app.models import Task, TimeSlot
from app.services.schedule_advance_notification_service import (
    capture_task_schedule_windows,
    notify_rescheduled_tasks_delayed,
    notify_rescheduled_tasks_advanced,
)
from app.services.task_delay_status_service import reset_task_delay


class ScheduleSlotNotFoundError(Exception):
    pass


class ScheduleSlotInvalidError(Exception):
    pass


def update_time_slot(db, slot_id: int, data) -> TimeSlot:
    slot = db.query(TimeSlot).filter(TimeSlot.id == slot_id).first()
    if not slot:
        raise ScheduleSlotNotFoundError("时间槽不存在")
    if slot.tier == "frozen":
        raise ScheduleSlotInvalidError("冻结期时间槽不可手动调整")

    original_windows = capture_task_schedule_windows(db, {slot.task_id})
    for field in ("plan_start", "plan_end", "instrument_id", "tier"):
        value = getattr(data, field, None)
        if value is not None:
            setattr(slot, field, value)

    task = db.query(Task).filter(Task.id == slot.task_id).first()
    if task and task.schedule_lock_status == "none":
        reset_task_delay(task)
    notify_rescheduled_tasks_advanced(db, original_windows, "手动调整排程")
    notify_rescheduled_tasks_delayed(db, original_windows, "手动调整排程")
    db.commit()
    db.refresh(slot)
    return slot

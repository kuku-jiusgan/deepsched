from __future__ import annotations

from collections import defaultdict

from app.models import Task, TimeSlot


class ScheduleConflictError(Exception):
    pass


ACTIVE_SLOT_STATUSES = ["scheduled", "running", "completed", "blocked", "interrupted"]


def find_instrument_conflicts(db) -> list[dict]:
    slots = db.query(TimeSlot).filter(
        TimeSlot.instrument_id.isnot(None),
        TimeSlot.status.in_(ACTIVE_SLOT_STATUSES),
    ).order_by(TimeSlot.instrument_id, TimeSlot.plan_start, TimeSlot.id).all()
    by_instrument: dict[int, list[tuple[TimeSlot, object, object]]] = defaultdict(list)
    for slot in slots:
        effective_range = _effective_slot_range(slot)
        if effective_range:
            by_instrument[slot.instrument_id].append((slot, *effective_range))

    conflicts = []
    for instrument_id, instrument_slots in by_instrument.items():
        instrument_slots.sort(key=lambda item: (item[1], item[0].id))
        previous = None
        for slot, start, end in instrument_slots:
            if previous and start < previous[2]:
                previous_slot, _, previous_end = previous
                conflicts.append({
                    "instrument_id": instrument_id,
                    "first_slot_id": previous_slot.id,
                    "second_slot_id": slot.id,
                    "first_task_id": previous_slot.task_id,
                    "second_task_id": slot.task_id,
                    "overlap_start": start.isoformat(),
                    "overlap_end": min(previous_end, end).isoformat(),
                })
                if end > previous_end:
                    previous = (slot, start, end)
                continue
            previous = (slot, start, end)
    return conflicts


def find_human_conflicts(db) -> list[dict]:
    slots = db.query(TimeSlot).join(Task).filter(
        Task.requires_human.is_(True),
        Task.assignee_id.isnot(None),
        TimeSlot.status.in_(ACTIVE_SLOT_STATUSES),
    ).order_by(Task.assignee_id, TimeSlot.plan_start, TimeSlot.id).all()
    by_assignee: dict[int, list[tuple[TimeSlot, object, object]]] = defaultdict(list)
    for slot in slots:
        effective_range = _effective_slot_range(slot)
        if effective_range:
            by_assignee[slot.task.assignee_id].append((slot, *effective_range))

    conflicts = []
    for assignee_id, assignee_slots in by_assignee.items():
        assignee_slots.sort(key=lambda item: (item[1], item[0].id))
        previous = None
        for slot, start, end in assignee_slots:
            if previous and start < previous[2]:
                previous_slot, _, previous_end = previous
                conflicts.append({
                    "assignee_id": assignee_id,
                    "first_slot_id": previous_slot.id,
                    "second_slot_id": slot.id,
                    "first_task_id": previous_slot.task_id,
                    "second_task_id": slot.task_id,
                    "overlap_start": start.isoformat(),
                    "overlap_end": min(previous_end, end).isoformat(),
                })
                if end > previous_end:
                    previous = (slot, start, end)
                continue
            previous = (slot, start, end)
    return conflicts


def _effective_slot_range(slot: TimeSlot):
    if slot.status != "completed":
        return slot.plan_start, slot.plan_end
    if slot.actual_start and slot.actual_end:
        return slot.actual_start, slot.actual_end
    return None


def ensure_no_instrument_conflicts(db) -> None:
    conflicts = find_instrument_conflicts(db)
    if not conflicts:
        return
    conflict = conflicts[0]
    raise ScheduleConflictError(
        "仪器排程冲突：时间槽 "
        f"{conflict['first_slot_id']} 与 {conflict['second_slot_id']} 时间重叠"
    )


def ensure_no_human_conflicts(db) -> None:
    conflicts = find_human_conflicts(db)
    if not conflicts:
        return
    conflict = conflicts[0]
    raise ScheduleConflictError(
        "人员排程冲突：负责人 "
        f"{conflict['assignee_id']} 的时间槽 "
        f"{conflict['first_slot_id']} 与 {conflict['second_slot_id']} 时间重叠"
    )

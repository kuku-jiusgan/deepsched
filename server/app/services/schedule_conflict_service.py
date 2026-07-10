from __future__ import annotations

from collections import defaultdict

from app.models import TimeSlot


class ScheduleConflictError(Exception):
    pass


ACTIVE_SLOT_STATUSES = ["scheduled", "running", "completed", "blocked", "interrupted"]


def find_instrument_conflicts(db) -> list[dict]:
    slots = db.query(TimeSlot).filter(
        TimeSlot.instrument_id.isnot(None),
        TimeSlot.status.in_(ACTIVE_SLOT_STATUSES),
    ).order_by(TimeSlot.instrument_id, TimeSlot.plan_start, TimeSlot.id).all()
    by_instrument: dict[int, list[TimeSlot]] = defaultdict(list)
    for slot in slots:
        by_instrument[slot.instrument_id].append(slot)

    conflicts = []
    for instrument_id, instrument_slots in by_instrument.items():
        previous = None
        for slot in instrument_slots:
            if previous and slot.plan_start < previous.plan_end:
                conflicts.append({
                    "instrument_id": instrument_id,
                    "first_slot_id": previous.id,
                    "second_slot_id": slot.id,
                    "first_task_id": previous.task_id,
                    "second_task_id": slot.task_id,
                    "overlap_start": slot.plan_start.isoformat(),
                    "overlap_end": min(previous.plan_end, slot.plan_end).isoformat(),
                })
                if slot.plan_end > previous.plan_end:
                    previous = slot
                continue
            previous = slot
    return conflicts


def ensure_no_instrument_conflicts(db) -> None:
    conflicts = find_instrument_conflicts(db)
    if not conflicts:
        return
    conflict = conflicts[0]
    raise ScheduleConflictError(
        "仪器排程冲突：时间槽 "
        f"{conflict['first_slot_id']} 与 {conflict['second_slot_id']} 时间重叠"
    )

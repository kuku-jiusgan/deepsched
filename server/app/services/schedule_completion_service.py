from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.models import Task, TimeSlot
from app.services.schedule_rule_service import get_solver_constraints
from app.services.scheduler_helpers import (
    is_allowed_calendar_day,
    load_calendar_days,
    time_horizon,
    working_time_bounds,
)

SCHEDULE_UNIT_MINUTES = 30


def complete_task_and_shift(
    db: Session,
    task_id: int,
    actual_end_time: datetime | None = None,
) -> dict:
    end_time = actual_end_time or datetime.now()
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return {"status": "error", "message": "未找到指定任务"}

    task.status = "done"
    task_slots = (
        db.query(TimeSlot)
        .filter(TimeSlot.task_id == task_id)
        .order_by(TimeSlot.plan_start)
        .all()
    )

    for slot in task_slots:
        if slot.plan_start > end_time:
            db.delete(slot)
            continue
        if slot.plan_end > end_time:
            slot.plan_end = end_time
        if slot.actual_start is None:
            slot.actual_start = slot.plan_start
        slot.actual_end = end_time
        slot.status = "completed"

    db.commit()
    return _forward_shift_same_project_work(db, task)


def _forward_shift_same_project_work(db: Session, completed_task: Task) -> dict:
    last_slot = (
        db.query(TimeSlot)
        .filter(TimeSlot.task_id == completed_task.id)
        .order_by(TimeSlot.plan_end.desc())
        .first()
    )
    instrument_id = last_slot.instrument_id if last_slot else None
    if not instrument_id:
        return {"status": "ok", "message": "任务已完成，无绑定仪器，无需前移排程"}

    released_at = last_slot.plan_end
    candidate_tasks = _load_forward_shift_candidates(
        db,
        completed_task.project_id,
        instrument_id,
        released_at,
    )
    if not candidate_tasks:
        return {"status": "ok", "message": "任务已完成，无同项目同仪器后续任务可前移"}

    working_options = _load_working_options(db, released_at)
    original_slots = {
        task.id: (
            db.query(TimeSlot)
            .filter(TimeSlot.task_id == task.id, TimeSlot.status == "scheduled")
            .order_by(TimeSlot.plan_start)
            .all()
        )
        for task in candidate_tasks
    }
    slot_snapshots = {
        task_id: [_snapshot_slot(slot) for slot in slots]
        for task_id, slots in original_slots.items()
    }

    for task_id in slot_snapshots:
        db.query(TimeSlot).filter(
            TimeSlot.task_id == task_id,
            TimeSlot.status == "scheduled",
        ).delete(synchronize_session=False)
    db.flush()

    moved = 0
    cursor = released_at
    for task in candidate_tasks:
        snapshots = slot_snapshots[task.id]
        if not snapshots:
            continue

        original_start = snapshots[0]["plan_start"]
        original_end = snapshots[-1]["plan_end"]
        duration_minutes = sum(
            int((slot["plan_end"] - slot["plan_start"]).total_seconds() / 60)
            for slot in snapshots
        )
        slot_instrument_id = snapshots[0]["instrument_id"]
        dependency_ready = _dependency_ready_time(db, task, released_at)
        earliest_start = max(cursor, dependency_ready)
        new_slots = _build_forward_slots(
            db,
            slot_instrument_id,
            duration_minutes,
            earliest_start,
            working_options,
        )

        if not new_slots or new_slots[0][0] >= original_start:
            _restore_slot_snapshots(db, snapshots)
            cursor = max(cursor, original_end)
            continue

        for start, end in new_slots:
            db.add(
                TimeSlot(
                    task_id=task.id,
                    instrument_id=slot_instrument_id,
                    plan_start=start,
                    plan_end=end,
                    tier=_tier_for_start(start),
                    status="scheduled",
                )
            )
        cursor = new_slots[-1][1]
        moved += 1

    db.commit()
    return {
        "status": "ok",
        "message": f"任务已完成，同项目同仪器前移 {moved} 个任务",
        "moved_tasks": moved,
    }


def _load_forward_shift_candidates(
    db: Session,
    project_id: int,
    instrument_id: int,
    released_at: datetime,
) -> list[Task]:
    first_start = func.min(TimeSlot.plan_start).label("first_start")
    candidate_rows = (
        db.query(Task.id, first_start)
        .join(TimeSlot, TimeSlot.task_id == Task.id)
        .filter(
            Task.project_id == project_id,
            Task.status == "scheduled",
            or_(
                TimeSlot.instrument_id == instrument_id,
                TimeSlot.instrument_id.is_(None),
            ),
            TimeSlot.status == "scheduled",
            TimeSlot.plan_start >= released_at,
        )
        .group_by(Task.id)
        .order_by(first_start)
        .all()
    )
    candidate_ids = [row[0] for row in candidate_rows]
    tasks_by_id = {
        task.id: task
        for task in db.query(Task)
        .options(selectinload(Task.predecessors))
        .filter(Task.id.in_(candidate_ids))
        .all()
    }
    return [tasks_by_id[task_id] for task_id in candidate_ids if task_id in tasks_by_id]


def _load_working_options(db: Session, released_at: datetime) -> dict:
    constraints = get_solver_constraints(db)
    working_rule = constraints["working_hours"]
    working_params = working_rule.params or {}
    day_start_minutes, day_end_minutes = working_time_bounds(working_params)
    include_weekends = bool(working_params.get("include_weekends", False))
    include_holidays = bool(working_params.get("include_holidays", False))
    if not working_rule.is_enabled:
        day_start_minutes, day_end_minutes = 0, 24 * 60
        include_weekends, include_holidays = True, True

    _, horizon_end, _ = time_horizon()
    return {
        "day_start_minutes": day_start_minutes,
        "day_end_minutes": day_end_minutes,
        "include_weekends": include_weekends,
        "include_holidays": include_holidays,
        "horizon_end": horizon_end,
        "calendar_days": load_calendar_days(db, released_at, horizon_end),
    }


def _dependency_ready_time(
    db: Session,
    task: Task,
    fallback: datetime,
) -> datetime:
    ready_time = fallback
    for dependency in task.predecessors:
        pred_end = (
            db.query(func.max(TimeSlot.plan_end))
            .filter(TimeSlot.task_id == dependency.predecessor_id)
            .scalar()
        )
        if pred_end and pred_end > ready_time:
            ready_time = pred_end
    return ready_time


def _build_forward_slots(
    db: Session,
    instrument_id: int | None,
    duration_minutes: int,
    earliest_start: datetime,
    working_options: dict,
) -> list[tuple[datetime, datetime]]:
    remaining = duration_minutes
    slots: list[tuple[datetime, datetime]] = []
    chunk_start: datetime | None = None
    cursor = _ceil_to_schedule_unit(earliest_start)

    while remaining > 0 and cursor < working_options["horizon_end"]:
        next_cursor = cursor + timedelta(minutes=SCHEDULE_UNIT_MINUTES)
        if _can_use_unit(db, instrument_id, cursor, next_cursor, working_options):
            if chunk_start is None:
                chunk_start = cursor
            remaining -= SCHEDULE_UNIT_MINUTES
        else:
            if chunk_start is not None:
                slots.append((chunk_start, cursor))
                chunk_start = None
        cursor = next_cursor

    if remaining <= 0 and chunk_start is not None:
        slots.append((chunk_start, cursor))
    if remaining > 0:
        return []
    return slots


def _can_use_unit(
    db: Session,
    instrument_id: int | None,
    start: datetime,
    end: datetime,
    working_options: dict,
) -> bool:
    current_minutes = start.hour * 60 + start.minute
    if (
        current_minutes < working_options["day_start_minutes"]
        or current_minutes >= working_options["day_end_minutes"]
        or not is_allowed_calendar_day(
            start.date(),
            working_options["calendar_days"],
            working_options["include_weekends"],
            working_options["include_holidays"],
        )
    ):
        return False
    if instrument_id is None:
        return True
    conflict = (
        db.query(TimeSlot.id)
        .filter(
            TimeSlot.instrument_id == instrument_id,
            TimeSlot.plan_start < end,
            TimeSlot.plan_end > start,
        )
        .first()
    )
    return conflict is None


def _ceil_to_schedule_unit(value: datetime) -> datetime:
    value = value.replace(second=0, microsecond=0)
    remainder = value.minute % SCHEDULE_UNIT_MINUTES
    if remainder == 0:
        return value
    value += timedelta(minutes=SCHEDULE_UNIT_MINUTES - remainder)
    return value.replace(second=0, microsecond=0)


def _snapshot_slot(slot: TimeSlot) -> dict:
    return {
        "task_id": slot.task_id,
        "instrument_id": slot.instrument_id,
        "plan_start": slot.plan_start,
        "plan_end": slot.plan_end,
        "tier": slot.tier,
        "status": slot.status,
    }


def _restore_slot_snapshots(db: Session, snapshots: list[dict]) -> None:
    for slot in snapshots:
        db.add(TimeSlot(**slot))


def _tier_for_start(start: datetime) -> str:
    settings = get_settings()
    now = datetime.now()
    if start <= now + timedelta(days=settings.FROZEN_DAYS):
        return "frozen"
    if start <= now + timedelta(days=settings.CONFIRMED_DAYS):
        return "confirmed"
    return "forecast"

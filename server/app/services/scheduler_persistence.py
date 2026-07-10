from __future__ import annotations

from datetime import datetime, timedelta

from app.core.config import get_settings
from app.models import TimeSlot
from app.services.scheduler_helpers import TIME_UNIT_MINUTES, is_allowed_calendar_day


def persist_slots(
    db,
    tasks,
    instruments,
    solver,
    task_starts,
    task_ends,
    presences,
    horizon_start,
    day_start_minutes: int,
    day_end_minutes: int,
    freeze_days: int,
    calendar_days=None,
    include_weekends: bool = False,
    include_holidays: bool = False,
    schedule_run_id: str = "legacy",
) -> int:
    now = datetime.now()
    frozen_boundary = now + timedelta(days=freeze_days)
    confirmed_boundary = now + timedelta(
        days=get_settings().CONFIRMED_DAYS
    )
    created = 0

    for task in tasks:
        assigned_instrument = _assigned_instrument(
            task,
            instruments,
            solver,
            presences,
        )
        if task.requires_instrument and assigned_instrument is None:
            continue

        start_unit = solver.Value(task_starts[task.id])
        end_unit = solver.Value(task_ends[task.id])
        chunk_start = None
        for unit in range(start_unit, end_unit):
            current = horizon_start + timedelta(
                minutes=unit * TIME_UNIT_MINUTES
            )
            current_minutes = current.hour * 60 + current.minute
            is_working = (
                day_start_minutes <= current_minutes < day_end_minutes
                and is_allowed_calendar_day(
                    current.date(),
                    calendar_days or {},
                    include_weekends,
                    include_holidays,
                )
            )
            if is_working and chunk_start is None:
                chunk_start = current
            elif not is_working and chunk_start is not None:
                _create_slot(
                    db,
                    task,
                    assigned_instrument,
                    chunk_start,
                    current,
                    frozen_boundary,
                    confirmed_boundary,
                    schedule_run_id,
                )
                created += 1
                chunk_start = None

        if chunk_start is not None:
            final_end = horizon_start + timedelta(
                minutes=end_unit * TIME_UNIT_MINUTES
            )
            _create_slot(
                db,
                task,
                assigned_instrument,
                chunk_start,
                final_end,
                frozen_boundary,
                confirmed_boundary,
                schedule_run_id,
            )
            created += 1
        task.status = "scheduled"

    db.commit()
    return created


def _assigned_instrument(task, instruments, solver, presences):
    if not task.requires_instrument:
        return None
    for instrument in instruments:
        key = (task.id, instrument.id)
        if key in presences and solver.Value(presences[key]) == 1:
            return instrument
    return None


def _create_slot(
    db,
    task,
    instrument,
    start,
    end,
    frozen_boundary,
    confirmed_boundary,
    schedule_run_id,
) -> None:
    if start <= frozen_boundary:
        tier = "frozen"
    elif start <= confirmed_boundary:
        tier = "confirmed"
    else:
        tier = "forecast"
    db.add(
        TimeSlot(
            task_id=task.id,
            schedule_run_id=schedule_run_id,
            instrument_id=instrument.id if instrument else None,
            plan_start=start,
            plan_end=end,
            tier=tier,
            status="scheduled",
        )
    )

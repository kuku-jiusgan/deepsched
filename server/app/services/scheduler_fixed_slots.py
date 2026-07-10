from __future__ import annotations

from collections import defaultdict

from ortools.sat.python import cp_model

from app.models import TimeSlot
from app.services.scheduler_helpers import datetime_to_units


FIXED_SLOT_STATUSES = ["scheduled", "running", "completed", "blocked", "interrupted"]


def load_fixed_slots(db, excluded_task_ids: set[int] | None = None) -> list[TimeSlot]:
    query = db.query(TimeSlot).filter(
        TimeSlot.instrument_id.isnot(None),
        TimeSlot.status.in_(FIXED_SLOT_STATUSES),
    )
    if excluded_task_ids:
        query = query.filter(~TimeSlot.task_id.in_(excluded_task_ids))
    return query.order_by(TimeSlot.instrument_id, TimeSlot.plan_start, TimeSlot.id).all()


def add_instrument_capacity_constraints(
    model: cp_model.CpModel,
    instruments,
    tasks,
    capacity_intervals,
    presences,
    inst_starts,
    inst_ends,
    split_unit_presences,
    fixed_slots: list[TimeSlot],
    horizon_start,
    total_units: int,
    non_overlap_enabled: bool,
    setup_units: int,
) -> None:
    fixed_by_instrument: dict[int, list[tuple[TimeSlot, int, int]]] = defaultdict(list)
    for slot in fixed_slots:
        start_unit = datetime_to_units(slot.plan_start, horizon_start)
        end_unit = datetime_to_units(slot.plan_end, horizon_start)
        if end_unit <= 0 or start_unit >= total_units:
            continue
        fixed_by_instrument[slot.instrument_id].append(
            (slot, max(0, start_unit), min(total_units, end_unit))
        )

    task_by_id = {task.id: task for task in tasks}
    for instrument in instruments:
        instrument_intervals = list(capacity_intervals.get(instrument.id, []))
        for slot, start_unit, end_unit in fixed_by_instrument.get(instrument.id, []):
            instrument_intervals.append(model.NewIntervalVar(
                start_unit,
                end_unit - start_unit,
                end_unit,
                f"fixed_slot_{slot.id}",
            ))

        if instrument_intervals and non_overlap_enabled:
            model.AddNoOverlap(instrument_intervals)

        if setup_units <= 0:
            continue
        for key, presence in presences.items():
            task_id, instrument_id = key
            if instrument_id != instrument.id:
                continue
            task = task_by_id[task_id]
            for slot, start_unit, end_unit in fixed_by_instrument.get(instrument.id, []):
                fixed_project_id = slot.task.project_id if slot.task else None
                if fixed_project_id == task.project_id:
                    continue
                if task.allow_split:
                    for split_key, unit_presence in split_unit_presences.items():
                        split_task_id, split_instrument_id, unit = split_key
                        if split_task_id != task_id or split_instrument_id != instrument.id:
                            continue
                        if unit < end_unit + setup_units and unit + 1 > start_unit - setup_units:
                            model.Add(unit_presence == 0)
                    continue
                before = model.NewBoolVar(f"t{task_id}_before_fixed_{slot.id}")
                after = model.NewBoolVar(f"t{task_id}_after_fixed_{slot.id}")
                model.Add(before + after == presence)
                model.Add(inst_ends[key] + setup_units <= start_unit).OnlyEnforceIf(before)
                model.Add(inst_starts[key] >= end_unit + setup_units).OnlyEnforceIf(after)

from __future__ import annotations

import json

from app.models import Instrument, TimeSlot
from app.services.scheduler_helpers import TIME_UNIT_MINUTES, datetime_to_units, to_units


def unavailable_instrument_message(db, tasks, compatibility: dict[int, list[Instrument]]) -> str | None:
    for task in tasks:
        if not task.requires_instrument or compatibility.get(task.id):
            continue

        instrument_ids = _parse_instrument_ids(task)
        if not instrument_ids:
            return f"排程失败：任务【{task.name}】没有可用仪器。"

        instruments = (
            db.query(Instrument)
            .filter(Instrument.id.in_(instrument_ids))
            .order_by(Instrument.id)
            .all()
        )
        faulted = [instrument for instrument in instruments if instrument.status == "fault"]
        if faulted:
            names = "、".join(_instrument_label(instrument) for instrument in faulted)
            return f"排程失败：仪器【{names}】故障，任务【{task.name}】排程失败。"

        names = "、".join(_instrument_label(instrument) for instrument in instruments)
        return f"排程失败：指定仪器【{names or '未知仪器'}】当前不可用，任务【{task.name}】排程失败。"
    return None


def frozen_schedule_message(
    tasks,
    compatibility: dict[int, list[Instrument]],
    fixed_slots: list[TimeSlot],
    instrument_prefix_sums: dict[int, list[int]],
    horizon_start,
    total_units: int,
    setup_units: int,
) -> str | None:
    frozen_by_instrument: dict[int, list[TimeSlot]] = {}
    for slot in fixed_slots:
        if slot.tier == "frozen":
            frozen_by_instrument.setdefault(slot.instrument_id, []).append(slot)

    for task in tasks:
        candidates = compatibility.get(task.id, [])
        instrument_ids = _parse_instrument_ids(task)
        if (
            not task.requires_instrument
            or not instrument_ids
            or not candidates
            or not task.project
            or not task.project.start_date
            or not task.project.end_date
        ):
            continue

        window_start = max(0, datetime_to_units(task.project.start_date, horizon_start))
        window_end = min(total_units, datetime_to_units(task.project.end_date, horizon_start))
        required_units = to_units(
            (task.est_duration_hours or 4) + (task.switchover_hours or 0)
        )
        if window_end <= window_start:
            continue
        if all(
            _working_units(
                instrument_prefix_sums[instrument.id],
                window_start,
                window_end,
            ) < required_units
            for instrument in candidates
        ):
            continue

        blocked_instruments = []
        for instrument in candidates:
            working_prefix_sum = instrument_prefix_sums[instrument.id]
            frozen_slots = frozen_by_instrument.get(instrument.id, [])
            gaps = _available_gaps(
                task,
                frozen_slots,
                horizon_start,
                window_start,
                window_end,
                setup_units,
            )
            available_units = [
                _working_units(working_prefix_sum, start, end)
                for start, end in gaps
            ]
            has_capacity = (
                sum(available_units) >= required_units
                if task.allow_split
                else any(units >= required_units for units in available_units)
            )
            if has_capacity:
                break
            if frozen_slots:
                blocked_instruments.append(instrument)
        else:
            if len(blocked_instruments) == len(candidates):
                names = "、".join(_instrument_label(item) for item in blocked_instruments)
                required_hours = required_units * TIME_UNIT_MINUTES / 60
                return (
                    f"排程失败：项目【{task.project.name}】时间窗口内，冻结期内指定仪器"
                    f"【{names}】日程已满，任务【{task.name}】需要约 {required_hours:g} 小时，"
                    "无法完成排程。请延长项目日期或调整冻结排程后重试。"
                )
    return None


def _available_gaps(
    task,
    frozen_slots: list[TimeSlot],
    horizon_start,
    window_start: int,
    window_end: int,
    setup_units: int,
) -> list[tuple[int, int]]:
    blocked_ranges = []
    for slot in frozen_slots:
        slot_start = datetime_to_units(slot.plan_start, horizon_start)
        slot_end = datetime_to_units(slot.plan_end, horizon_start)
        if slot_end <= window_start or slot_start >= window_end:
            continue
        padding = setup_units if slot.task and slot.task.project_id != task.project_id else 0
        blocked_ranges.append((
            max(window_start, slot_start - padding),
            min(window_end, slot_end + padding),
        ))

    cursor = window_start
    gaps = []
    for blocked_start, blocked_end in sorted(blocked_ranges):
        if blocked_start > cursor:
            gaps.append((cursor, blocked_start))
        cursor = max(cursor, blocked_end)
    if cursor < window_end:
        gaps.append((cursor, window_end))
    return gaps


def _working_units(prefix_sum: list[int], start: int, end: int) -> int:
    safe_start = max(0, min(start, len(prefix_sum) - 1))
    safe_end = max(safe_start, min(end, len(prefix_sum) - 1))
    return prefix_sum[safe_end] - prefix_sum[safe_start]

def _instrument_label(instrument: Instrument) -> str:
    return f"{instrument.name}({instrument.code})"


def _parse_instrument_ids(task) -> list[int]:
    raw_ids = getattr(task, "instrument_ids", None)
    if not raw_ids:
        return []
    if isinstance(raw_ids, str):
        try:
            raw_ids = json.loads(raw_ids)
        except (json.JSONDecodeError, ValueError):
            raw_ids = [item.strip() for item in raw_ids.split(",") if item.strip()]
    if isinstance(raw_ids, list):
        return [int(instrument_id) for instrument_id in raw_ids]
    return [int(raw_ids)]

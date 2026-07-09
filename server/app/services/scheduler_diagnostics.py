from __future__ import annotations

import json

from app.models import Instrument


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

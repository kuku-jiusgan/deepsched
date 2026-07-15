from __future__ import annotations

from sqlalchemy import not_, select
from sqlalchemy.orm import selectinload

from app.models import Instrument, Task


def load_scheduler_data(db, project_ids=None, task_ids=None):
    child_parent_ids = select(Task.parent_id).where(Task.parent_id.isnot(None))
    query = db.query(Task).filter(
        Task.status.in_(["pending", "ready"]),
        Task.is_external_gate.is_(False),
        not_(Task.id.in_(child_parent_ids)),
    ).options(
        selectinload(Task.project),
        selectinload(Task.milestone),
        selectinload(Task.predecessors),
        selectinload(Task.capability_requirements),
    )
    if project_ids:
        query = query.filter(Task.project_id.in_(project_ids))
    if task_ids:
        query = query.filter(Task.id.in_(task_ids))
    tasks = query.order_by(Task.priority_weight.desc(), Task.created_at, Task.id).all()

    instruments = db.query(Instrument).filter(
        Instrument.availability_status == "available",
        Instrument.status.in_(["idle", "running"]),
    ).options(
        selectinload(Instrument.capabilities),
        selectinload(Instrument.maintenance_windows),
    ).all()
    return tasks, instruments

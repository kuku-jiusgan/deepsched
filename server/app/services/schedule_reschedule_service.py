from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Task, TimeSlot
from app.schemas.schemas import RescheduleRequest


def reschedule(db: Session, data: RescheduleRequest) -> dict:
    if data.strategy == "local":
        return _local_repair(db, data)
    if data.strategy == "project":
        return _project_reschedule(db, data)
    return _global_reschedule(db)


def _local_repair(db: Session, data: RescheduleRequest) -> dict:
    if data.affected_task_id:
        task = db.query(Task).filter(Task.id == data.affected_task_id).first()
        if task and task.status not in {"running", "done", "completed"}:
            db.query(TimeSlot).filter(
                TimeSlot.task_id == data.affected_task_id,
                TimeSlot.tier.in_(["confirmed", "forecast"]),
                TimeSlot.status.in_(["scheduled", "blocked"]),
            ).delete()
            task.status = "pending"
            db.commit()
    return _generate(db)


def _project_reschedule(db: Session, data: RescheduleRequest) -> dict:
    if data.affected_task_id:
        task = db.query(Task).filter(Task.id == data.affected_task_id).first()
        if task and task.status not in {"running", "done", "completed"}:
            db.query(TimeSlot).filter(
                TimeSlot.task_id.in_(
                    db.query(Task.id).filter(Task.project_id == task.project_id)
                ),
                TimeSlot.tier.in_(["confirmed", "forecast"]),
                TimeSlot.status.in_(["scheduled", "blocked"]),
            ).delete()
            db.query(Task).filter(
                Task.project_id == task.project_id,
                Task.status == "scheduled",
            ).update({"status": "pending"})
            db.commit()
            return _generate(db, [task.project_id])
    return {"status": "error", "message": "未指定受影响任务"}


def _global_reschedule(db: Session) -> dict:
    db.query(TimeSlot).filter(
        TimeSlot.tier.in_(["confirmed", "forecast"]),
        TimeSlot.status.in_(["scheduled", "blocked"]),
    ).delete()
    db.query(Task).filter(Task.status == "scheduled").update({"status": "pending"})
    result = _generate(db, commit=False)
    if result.get("status") == "ok":
        db.commit()
    else:
        db.rollback()
    return result


def _generate(
    db: Session,
    project_ids: list[int] | None = None,
    commit: bool = True,
) -> dict:
    from app.services.scheduler import SchedulerService

    return SchedulerService(db).generate(project_ids, commit=commit)

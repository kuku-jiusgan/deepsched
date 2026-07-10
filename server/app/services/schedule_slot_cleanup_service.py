from sqlalchemy.orm import Session

from app.models import Task, TimeSlot


def clear_reschedulable_slots(db: Session, project_ids: list[int] | None = None) -> None:
    done_task_ids = db.query(Task.id).filter(Task.status == "done").distinct()

    if project_ids:
        project_task_ids = db.query(Task.id).filter(Task.project_id.in_(project_ids))
        db.query(TimeSlot).filter(
            TimeSlot.task_id.in_(project_task_ids),
            TimeSlot.status.in_(["scheduled", "blocked"]),
            ~TimeSlot.task_id.in_(done_task_ids),
        ).delete(synchronize_session=False)

        db.query(Task).filter(
            Task.project_id.in_(project_ids),
            Task.status.in_(["scheduled", "blocked"]),
            ~Task.id.in_(done_task_ids),
        ).update({"status": "pending"}, synchronize_session=False)
        db.commit()
        return

    frozen_task_ids = db.query(TimeSlot.task_id).filter(
        TimeSlot.tier == "frozen"
    ).distinct()

    db.query(TimeSlot).filter(
        TimeSlot.tier.in_(["forecast", "confirmed"]),
        TimeSlot.status.in_(["scheduled", "blocked"]),
        ~TimeSlot.task_id.in_(frozen_task_ids),
        ~TimeSlot.task_id.in_(done_task_ids),
    ).delete(synchronize_session=False)

    db.query(Task).filter(
        Task.status.in_(["scheduled", "blocked"]),
        ~Task.id.in_(frozen_task_ids),
    ).update({"status": "pending"}, synchronize_session=False)

    db.commit()

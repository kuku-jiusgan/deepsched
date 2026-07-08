from sqlalchemy.orm import Session

from app.models import Task, TimeSlot


def clear_reschedulable_slots(db: Session) -> None:
    frozen_task_ids = db.query(TimeSlot.task_id).filter(
        TimeSlot.tier == "frozen"
    ).distinct()
    done_task_ids = db.query(Task.id).filter(Task.status == "done").distinct()

    db.query(TimeSlot).filter(
        TimeSlot.tier.in_(["forecast", "confirmed"]),
        ~TimeSlot.task_id.in_(frozen_task_ids),
        ~TimeSlot.task_id.in_(done_task_ids),
    ).delete(synchronize_session=False)

    db.query(Task).filter(
        Task.status.in_(["scheduled", "blocked"]),
        ~Task.id.in_(frozen_task_ids),
    ).update({"status": "pending"}, synchronize_session=False)

    db.commit()

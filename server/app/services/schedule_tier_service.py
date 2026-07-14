from datetime import datetime, timedelta

from app.core.config import get_settings
from app.models import TimeSlot
from app.services.schedule_rule_service import get_solver_constraints
from app.services.scheduler_helpers import natural_day_boundary


RECALCULABLE_STATUSES = ["scheduled", "blocked"]


def roll_schedule_tiers(db, now: datetime | None = None) -> dict:
    current_time = now or datetime.now()
    settings = get_settings()
    freezing_rule = get_solver_constraints(db)["freezing"]
    freeze_days = int((freezing_rule.params or {}).get("freeze_days", settings.FROZEN_DAYS))
    frozen_boundary = natural_day_boundary(current_time, freeze_days)
    confirmed_boundary = current_time + timedelta(days=settings.CONFIRMED_DAYS)

    eligible = [
        TimeSlot.status.in_(RECALCULABLE_STATUSES),
        TimeSlot.actual_start.is_(None),
    ]
    db.query(TimeSlot).filter(
        *eligible,
        TimeSlot.plan_start <= frozen_boundary,
    ).update({"tier": "frozen"}, synchronize_session=False)
    db.query(TimeSlot).filter(
        *eligible,
        TimeSlot.plan_start > frozen_boundary,
        TimeSlot.plan_start <= confirmed_boundary,
    ).update({"tier": "confirmed"}, synchronize_session=False)
    db.query(TimeSlot).filter(
        *eligible,
        TimeSlot.plan_start > confirmed_boundary,
    ).update({"tier": "forecast"}, synchronize_session=False)
    db.commit()
    return {
        "status": "ok",
        "rolled_at": current_time.isoformat(),
        "frozen_until": frozen_boundary.isoformat(),
    }

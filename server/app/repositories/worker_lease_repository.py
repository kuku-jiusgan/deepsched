from datetime import datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.models import WorkerLease


def acquire_worker_lease(db, name: str, owner_id: str, ttl_seconds: int) -> bool:
    now = datetime.now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    updated = (
        db.query(WorkerLease)
        .filter(
            WorkerLease.name == name,
            or_(WorkerLease.expires_at <= now, WorkerLease.owner_id == owner_id),
        )
        .update(
            {
                WorkerLease.owner_id: owner_id,
                WorkerLease.expires_at: expires_at,
                WorkerLease.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    if updated:
        db.commit()
        return True

    try:
        db.add(WorkerLease(
            name=name,
            owner_id=owner_id,
            expires_at=expires_at,
            updated_at=now,
        ))
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        return False

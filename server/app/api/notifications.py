from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.models import Notification
from app.schemas.schemas import NotificationOut

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

@router.get("/history", response_model=List[NotificationOut])
def list_notification_history(limit: int = 200, db: Session = Depends(get_db)):
    safe_limit = min(max(limit, 1), 500)
    return (
        db.query(Notification)
        .order_by(Notification.created_at.desc())
        .limit(safe_limit)
        .all()
    )

@router.get("", response_model=List[NotificationOut])
def list_notifications(
    user_name: str = "default",
    channel: Optional[str] = None,
    unread_only: bool = False,
    db: Session = Depends(get_db),
):
    query = db.query(Notification).filter(Notification.user_name == user_name)
    if channel:
        query = query.filter(Notification.channel == channel)
    if unread_only:
        query = query.filter(Notification.is_read == False)
    return query.order_by(Notification.created_at.desc()).limit(50).all()

@router.put("/{nid}/read")
def mark_read(nid: int, db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == nid).first()
    if n:
        n.is_read = True
        db.commit()
    return {"status": "ok"}

@router.post("/{nid}/confirm")
def confirm(nid: int, db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.id == nid).first()
    if n:
        n.is_confirmed = True
        db.commit()
    return {"status": "ok"}

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models import Notification
from app.schemas.schemas import NotificationOut

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])

@router.get("", response_model=List[NotificationOut])
def list_notifications(user_name: str = "default", db: Session = Depends(get_db)):
    return db.query(Notification).filter(
        Notification.user_name == user_name
    ).order_by(Notification.created_at.desc()).limit(50).all()

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

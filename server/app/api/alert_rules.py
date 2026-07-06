from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import AlertRule
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/alert-rules", tags=["alert-rules"])

class AlertRuleOut(BaseModel):
    id: int
    name: str
    rule_type: str
    enabled: bool
    notify_roles: Optional[str] = None
    threshold_minutes: int = 0
    threshold_percent: int = 0
    model_config = {"from_attributes": True}

class AlertRuleUpdate(BaseModel):
    enabled: Optional[bool] = None
    notify_roles: Optional[str] = None
    threshold_minutes: Optional[int] = None
    threshold_percent: Optional[int] = None

@router.get("", response_model=List[AlertRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return db.query(AlertRule).all()

@router.put("/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: int, data: AlertRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    if data.enabled is not None:
        rule.enabled = data.enabled
    if data.notify_roles is not None:
        rule.notify_roles = data.notify_roles
    if data.threshold_minutes is not None:
        rule.threshold_minutes = data.threshold_minutes
    if data.threshold_percent is not None:
        rule.threshold_percent = data.threshold_percent
    db.commit()
    db.refresh(rule)
    return rule

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models.models import AlertRule
from app.services.push_notification_service import get_push_config, update_push_config
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/v1/alert-rules", tags=["alert-rules"])

class AlertRuleOut(BaseModel):
    id: int
    name: str
    rule_type: str
    enabled: bool
    enable_site: bool = True
    enable_wecom: bool = False
    notify_roles: Optional[str] = None
    threshold_minutes: int = 0
    threshold_percent: int = 0
    model_config = {"from_attributes": True}

class AlertRuleUpdate(BaseModel):
    enabled: Optional[bool] = None
    enable_site: Optional[bool] = None
    enable_wecom: Optional[bool] = None
    notify_roles: Optional[str] = None
    threshold_minutes: Optional[int] = None
    threshold_percent: Optional[int] = None

class PushChannelConfigOut(BaseModel):
    id: int
    wecom_enabled: bool = False
    wecom_corp_id: Optional[str] = None
    wecom_agent_id: Optional[str] = None
    wecom_secret: Optional[str] = None
    model_config = {"from_attributes": True}

class PushChannelConfigUpdate(BaseModel):
    wecom_enabled: Optional[bool] = None
    wecom_corp_id: Optional[str] = None
    wecom_agent_id: Optional[str] = None
    wecom_secret: Optional[str] = None

DEFAULT_ALERT_RULES = [
    {
        "name": "任务开始延迟",
        "rule_type": "task_start_delay",
        "enabled": True,
        "notify_roles": '["项目负责人","分析员"]',
        "threshold_minutes": 30,
        "threshold_percent": 0,
    },
    {
        "name": "任务结束延期",
        "rule_type": "task_end_delay",
        "enabled": True,
        "notify_roles": '["项目负责人","分析员"]',
        "threshold_minutes": 0,
        "threshold_percent": 0,
    },
    {
        "name": "排程变更通知",
        "rule_type": "schedule_changed",
        "enabled": True,
        "notify_roles": '["项目负责人"]',
        "threshold_minutes": 0,
        "threshold_percent": 0,
    },
    {
        "name": "实际工时超标",
        "rule_type": "hours_exceeded",
        "enabled": True,
        "notify_roles": '["项目负责人"]',
        "threshold_minutes": 0,
        "threshold_percent": 120,
    },
    {
        "name": "仪器故障后移",
        "rule_type": "instrument_fault_reschedule",
        "enabled": True,
        "notify_roles": '["项目负责人","分析员"]',
        "threshold_minutes": 0,
        "threshold_percent": 0,
    },
    {
        "name": "故障排程冲突",
        "rule_type": "instrument_fault_schedule_conflict",
        "enabled": True,
        "notify_roles": '["项目负责人"]',
        "threshold_minutes": 0,
        "threshold_percent": 0,
    },
]

@router.get("", response_model=List[AlertRuleOut])
def list_rules(db: Session = Depends(get_db)):
    _ensure_default_rules(db)
    return db.query(AlertRule).order_by(AlertRule.id).all()

@router.get("/push-config", response_model=PushChannelConfigOut)
def get_config(db: Session = Depends(get_db)):
    return get_push_config(db)

@router.put("/push-config", response_model=PushChannelConfigOut)
def save_config(data: PushChannelConfigUpdate, db: Session = Depends(get_db)):
    return update_push_config(db, data.model_dump(exclude_unset=True))

@router.put("/{rule_id}", response_model=AlertRuleOut)
def update_rule(rule_id: int, data: AlertRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    if data.enabled is not None:
        rule.enabled = data.enabled
    if data.enable_site is not None:
        rule.enable_site = data.enable_site
    if data.enable_wecom is not None:
        rule.enable_wecom = data.enable_wecom
    if data.notify_roles is not None:
        rule.notify_roles = data.notify_roles
    if data.threshold_minutes is not None:
        rule.threshold_minutes = data.threshold_minutes
    if data.threshold_percent is not None:
        rule.threshold_percent = data.threshold_percent
    db.commit()
    db.refresh(rule)
    return rule


def _ensure_default_rules(db: Session) -> None:
    existing_types = {row[0] for row in db.query(AlertRule.rule_type).all()}
    created = False
    for data in DEFAULT_ALERT_RULES:
        if data["rule_type"] in existing_types:
            continue
        db.add(AlertRule(**data))
        created = True
    if created:
        db.commit()

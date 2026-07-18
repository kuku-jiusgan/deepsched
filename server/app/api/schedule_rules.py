from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import ScheduleRuleOut, ScheduleRuleUpdate
from app.services import schedule_rule_service
from app.api.access import require_management_user


router = APIRouter(
    prefix="/api/v1/schedule-rules",
    tags=["schedule-rules"],
)


@router.get("", response_model=List[ScheduleRuleOut])
def list_rules(db: Session = Depends(get_db)):
    return schedule_rule_service.list_rules(db)


@router.put("/{rule_id}", response_model=ScheduleRuleOut)
def update_rule(
    rule_id: int,
    data: ScheduleRuleUpdate,
    db: Session = Depends(get_db),
    _user=Depends(require_management_user),
):
    try:
        return schedule_rule_service.update_rule(db, rule_id, data)
    except schedule_rule_service.ScheduleRuleNotFoundError:
        raise HTTPException(status_code=404, detail="规则不存在")
    except schedule_rule_service.ScheduleRuleLockedError:
        raise HTTPException(status_code=400, detail="该约束为求解器必选项")


@router.put("/{rule_id}/toggle", response_model=ScheduleRuleOut)
def toggle_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_management_user),
):
    try:
        return schedule_rule_service.toggle_rule(db, rule_id)
    except schedule_rule_service.ScheduleRuleNotFoundError:
        raise HTTPException(status_code=404, detail="规则不存在")
    except schedule_rule_service.ScheduleRuleLockedError:
        raise HTTPException(status_code=400, detail="该约束为求解器必选项")

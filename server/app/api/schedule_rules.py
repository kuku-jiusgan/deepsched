from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.models import ScheduleRule
from app.schemas.schemas import ScheduleRuleOut, ScheduleRuleUpdate

router = APIRouter(prefix="/api/v1/schedule-rules", tags=["schedule-rules"])

DEFAULT_RULES = [
    {"category":"decision_variable","name":"时间粒度","code":"time_granularity","description":"排程最小时间单位，单位为分钟","params":{"value":30,"unit":"分钟","options":[15,30,60]},"sort_order":1},
    {"category":"decision_variable","name":"规划窗口","code":"planning_horizon","description":"从当前时刻起向前规划的时长","params":{"value":90,"unit":"天","options":[30,60,90,120]},"sort_order":2},
    {"category":"constraint","name":"仪器分配","code":"instrument_assignment","description":"每个任务必须分配到恰好一台兼容仪器","params":{"strict":True},"sort_order":10},
    {"category":"constraint","name":"能力匹配","code":"capability_matching","description":"任务的能力标签要求必须匹配仪器已配置的能力标签","params":{"strict":True},"sort_order":11},
    {"category":"constraint","name":"仪器不重叠","code":"non_overlap","description":"同一台仪器上的任务时间区间不能重叠","params":{"strict":True},"sort_order":12},
    {"category":"constraint","name":"前置依赖","code":"precedence","description":"任务必须在所有前置任务完成后才能开始","params":{"strict":True},"sort_order":13},
    {"category":"constraint","name":"自动化任务夜间窗口","code":"automated_night_window","description":"自动化任务（无人值守）自动分配到夜间22:00-次日08:00执行","params":{"night_start":22,"night_end":8,"strict":False},"sort_order":14},
    {"category":"constraint","name":"人工作业时间限制","code":"manual_hours","description":"人工作业（前处理/配液等）不得跨越夜间窗口","params":{"day_start":8,"day_end":22,"strict":True},"sort_order":15},
    {"category":"constraint","name":"维护窗口避让","code":"maintenance_avoidance","description":"任务不得安排在仪器的计划维护时段内","params":{"strict":True},"sort_order":16},
    {"category":"constraint","name":"缓冲率","code":"buffer_rate","description":"按仪器的缓冲率系数放大任务预估时长，吸收实验偏差","params":{"enabled":True},"sort_order":17},
    {"category":"constraint","name":"切换代价","code":"switchover_cost","description":"同一仪器上切换不同项目/方法时增加切换准备时间","params":{"enabled":True,"base_hours":0.5},"sort_order":18},
    {"category":"constraint","name":"冻结锁定","code":"freezing","description":"已锁定的任务在重排时不被移动","params":{"enabled":True,"freeze_horizon_hours":72},"sort_order":19},
    {"category":"objective","name":"最小化加权延迟","code":"weighted_tardiness","description":"主目标：优先级越高的任务延迟惩罚越重，优先保证高优先级任务的准时性","params":{"weight":1.0,"enabled":True},"sort_order":30},
    {"category":"objective","name":"最小化最大完工时间","code":"makespan","description":"次目标：压缩整体排程周期，提高仪器周转效率","params":{"weight":0.3,"enabled":True},"sort_order":31},
    {"category":"objective","name":"最小化切换代价","code":"switchover_cost_obj","description":"次目标：减少同一仪器上项目/方法切换次数","params":{"weight":0.2,"enabled":True},"sort_order":32},
]

def _seed_rules(db: Session):
    existing = db.query(ScheduleRule).count()
    if existing > 0:
        return
    for r in DEFAULT_RULES:
        db.add(ScheduleRule(**r))
    db.commit()

@router.get("", response_model=List[ScheduleRuleOut])
def list_rules(db: Session = Depends(get_db)):
    _seed_rules(db)
    return db.query(ScheduleRule).order_by(ScheduleRule.sort_order).all()

@router.put("/{rule_id}", response_model=ScheduleRuleOut)
def update_rule(rule_id: int, data: ScheduleRuleUpdate, db: Session = Depends(get_db)):
    rule = db.query(ScheduleRule).filter(ScheduleRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    if data.params is not None:
        rule.params = data.params
    if data.is_enabled is not None:
        rule.is_enabled = data.is_enabled
    if data.sort_order is not None:
        rule.sort_order = data.sort_order
    db.commit()
    db.refresh(rule)
    return rule

@router.put("/{rule_id}/toggle", response_model=ScheduleRuleOut)
def toggle_rule(rule_id: int, db: Session = Depends(get_db)):
    rule = db.query(ScheduleRule).filter(ScheduleRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="规则不存在")
    rule.is_enabled = not rule.is_enabled
    db.commit()
    db.refresh(rule)
    return rule

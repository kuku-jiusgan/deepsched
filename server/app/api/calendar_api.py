from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, timedelta, datetime
from app.core.database import get_db
from app.models.models import SysCalendar
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/calendar", tags=["calendar"])

class CalendarDayOut(BaseModel):
    id: int
    date: date
    is_working_day: bool
    holiday_name: Optional[str] = None
    day_type: str = "workday"
    model_config = {"from_attributes": True}

class CalendarDayUpdate(BaseModel):
    is_working_day: Optional[bool] = None
    holiday_name: Optional[str] = None
    day_type: Optional[str] = None

class BatchFillRequest(BaseModel):
    year: int

@router.get("", response_model=List[CalendarDayOut])
def list_calendar(
    year: int = Query(None),
    month: int = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(SysCalendar)
    if year:
        q = q.filter(SysCalendar.date >= date(year, 1, 1), SysCalendar.date <= date(year, 12, 31))
    if month and year:
        q = q.filter(SysCalendar.date >= date(year, month, 1))
        if month == 12:
            q = q.filter(SysCalendar.date <= date(year, 12, 31))
        else:
            q = q.filter(SysCalendar.date < date(year, month + 1, 1))
    return q.order_by(SysCalendar.date).all()

@router.put("/{day_id}", response_model=CalendarDayOut)
def update_day(day_id: int, data: CalendarDayUpdate, db: Session = Depends(get_db)):
    day = db.query(SysCalendar).filter(SysCalendar.id == day_id).first()
    if not day:
        raise HTTPException(status_code=404, detail="日期不存在")
    if data.is_working_day is not None:
        day.is_working_day = data.is_working_day
    if data.holiday_name is not None:
        day.holiday_name = data.holiday_name
    if data.day_type is not None:
        day.day_type = data.day_type
    day.updated_at = datetime.now()
    db.commit()
    db.refresh(day)
    return day

@router.put("/date/{dt}", response_model=CalendarDayOut)
def upsert_date(dt: str, data: CalendarDayUpdate, db: Session = Depends(get_db)):
    d = date.fromisoformat(dt)
    day = db.query(SysCalendar).filter(SysCalendar.date == d).first()
    if not day:
        day = SysCalendar(date=d, is_working_day=True, day_type="workday")
        db.add(day)
        db.flush()
    if data.is_working_day is not None:
        day.is_working_day = data.is_working_day
    if data.holiday_name is not None:
        day.holiday_name = data.holiday_name
    if data.day_type is not None:
        day.day_type = data.day_type
    day.updated_at = datetime.now()
    db.commit()
    db.refresh(day)
    return day

@router.post("/batch-fill")
def batch_fill(data: BatchFillRequest, db: Session = Depends(get_db)):
    """预填充指定年份的日历，按常规周末模式（周六日休息）占位"""
    year = data.year
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    current = start
    count = 0
    while current <= end:
        existing = db.query(SysCalendar).filter(SysCalendar.date == current).first()
        if not existing:
            dow = current.weekday()  # 0=Mon, 6=Sun
            is_work = dow < 5
            db.add(SysCalendar(
                date=current,
                is_working_day=is_work,
                day_type="workday" if is_work else "weekend",
                created_at=datetime.now(),
                updated_at=datetime.now()
            ))
            count += 1
        current += timedelta(days=1)
    db.commit()
    return {"detail": f"已填充 {count} 天", "year": year}

@router.get("/is-workday/{dt}")
def check_workday(dt: str, db: Session = Depends(get_db)):
    d = date.fromisoformat(dt)
    day = db.query(SysCalendar).filter(SysCalendar.date == d).first()
    if day:
        return {"date": dt, "is_working_day": day.is_working_day, "holiday_name": day.holiday_name, "day_type": day.day_type}
    # Default: weekend check
    is_work = d.weekday() < 5
    return {"date": dt, "is_working_day": is_work, "holiday_name": None, "day_type": "workday" if is_work else "weekend"}
@router.post("/sync/{year}")
def sync_holidays(year: int, db: Session = Depends(get_db)):
    """从 timor.tech API 同步指定年份的节假日数据"""
    import urllib.request, json as jmod
    url = f"https://timor.tech/api/holiday/year/{year}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        resp = urllib.request.urlopen(req, timeout=10)
        data = jmod.loads(resp.read().decode())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"API请求失败: {str(e)}")

    if data.get("code") != 0:
        raise HTTPException(status_code=502, detail=f"API返回异常: {data.get('msg', '未知错误')}")

    holidays = data.get("holiday", {})
    if not holidays:
        raise HTTPException(status_code=404, detail=f"未找到{year}年节假日数据")

    updated = 0
    created = 0
    for date_str, info in holidays.items():
        # Keys are MM-DD format, prepend year
        d = date.fromisoformat(f"{year}-{date_str}")
        hol = info.get("holiday", False) if isinstance(info, dict) else bool(info)
        name = info.get("name", "") if isinstance(info, dict) else ""
        is_work = not hol  # holiday -> not working day

        existing = db.query(SysCalendar).filter(SysCalendar.date == d).first()
        if existing:
            existing.is_working_day = is_work
            existing.holiday_name = name if hol else None
            existing.day_type = "holiday" if hol else "workday"
            existing.updated_at = datetime.now()
            updated += 1
        else:
            db.add(SysCalendar(
                date=d,
                is_working_day=is_work,
                holiday_name=name if hol else None,
                day_type="holiday" if hol else "workday",
                created_at=datetime.now(),
                updated_at=datetime.now()
            ))
            created += 1

    db.commit()
    return {"detail": f"同步完成: 更新{updated}天, 新增{created}天", "year": year}


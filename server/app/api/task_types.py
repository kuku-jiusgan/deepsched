from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.models import TaskTypeConfig

router = APIRouter(prefix="/api/v1/task-types", tags=["task-types"])

class TaskTypeCreate(BaseModel):
    name: str
    code: str
    resource_type: str = "both"
    description: Optional[str] = None
    is_active: bool = True
    sort_order: int = 0

class TaskTypeOut(BaseModel):
    id: int
    name: str
    code: str
    resource_type: str
    description: Optional[str]
    is_active: bool
    sort_order: int
    model_config = {"from_attributes": True}

@router.get("", response_model=List[TaskTypeOut])
def list_task_types(db: Session = Depends(get_db)):
    return db.query(TaskTypeConfig).order_by(TaskTypeConfig.sort_order).all()

@router.post("", response_model=TaskTypeOut)
def create_task_type(data: TaskTypeCreate, db: Session = Depends(get_db)):
    existing = db.query(TaskTypeConfig).filter(TaskTypeConfig.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="类型编码已存在")
    item = TaskTypeConfig(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.put("/{item_id}", response_model=TaskTypeOut)
def update_task_type(item_id: int, data: TaskTypeCreate, db: Session = Depends(get_db)):
    item = db.query(TaskTypeConfig).filter(TaskTypeConfig.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="任务类型不存在")
    existing = db.query(TaskTypeConfig).filter(TaskTypeConfig.code == data.code, TaskTypeConfig.id != item_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="类型编码已存在")
    for k, v in data.model_dump().items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{item_id}")
def delete_task_type(item_id: int, db: Session = Depends(get_db)):
    item = db.query(TaskTypeConfig).filter(TaskTypeConfig.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="任务类型不存在")
    db.delete(item)
    db.commit()
    return {"detail": "已删除"}

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
from app.core.database import get_db
from app.models import TaskTypeConfig
from app.api.access import require_management_user

router = APIRouter(prefix="/api/v1/task-types", tags=["task-types"])

class TaskTypeCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    resource_type: str = "both"
    description: Optional[str] = Field(default=None, max_length=500)
    is_active: bool = True
    sort_order: int = 0
    predecessor_type_ids: List[int] = Field(default_factory=list, max_length=100)

class TaskTypeOut(BaseModel):
    id: int
    name: str
    code: str
    resource_type: str
    description: Optional[str]
    is_active: bool
    sort_order: int
    predecessor_type_ids: List[int] = Field(default_factory=list)
    model_config = {"from_attributes": True}

    @field_validator("predecessor_type_ids", mode="before")
    @classmethod
    def normalize_predecessor_type_ids(cls, value):
        return value or []

class TaskTypeToggle(BaseModel):
    is_active: bool

@router.get("", response_model=List[TaskTypeOut])
def list_task_types(db: Session = Depends(get_db)):
    return db.query(TaskTypeConfig).order_by(TaskTypeConfig.sort_order).all()

@router.post("", response_model=TaskTypeOut)
def create_task_type(
    data: TaskTypeCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_management_user),
):
    existing = db.query(TaskTypeConfig).filter(TaskTypeConfig.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="类型编码已存在")
    item = TaskTypeConfig(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item

@router.put("/{item_id}", response_model=TaskTypeOut)
def update_task_type(
    item_id: int,
    data: TaskTypeCreate,
    db: Session = Depends(get_db),
    _user=Depends(require_management_user),
):
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

@router.put("/{item_id}/toggle", response_model=TaskTypeOut)
def toggle_task_type(
    item_id: int,
    data: TaskTypeToggle,
    db: Session = Depends(get_db),
    _user=Depends(require_management_user),
):
    item = db.query(TaskTypeConfig).filter(TaskTypeConfig.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="任务类型不存在")
    item.is_active = data.is_active
    db.commit()
    db.refresh(item)
    return item

@router.delete("/{item_id}")
def delete_task_type(
    item_id: int,
    db: Session = Depends(get_db),
    _user=Depends(require_management_user),
):
    item = db.query(TaskTypeConfig).filter(TaskTypeConfig.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="任务类型不存在")
    db.delete(item)
    db.commit()
    return {"detail": "已删除"}

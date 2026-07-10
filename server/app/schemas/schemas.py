from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

# ---- Project ----
class MilestoneCreate(BaseModel):
    name: str
    due_date: datetime

class MilestoneOut(BaseModel):
    id: int
    project_id: int
    name: str
    due_date: datetime
    status: str
    model_config = ConfigDict(from_attributes=True)

class TaskCapabilityReqCreate(BaseModel):
    tag_name: str
    tag_value: str

class TaskCapabilityReqOut(BaseModel):
    id: int
    tag_name: str
    tag_value: str
    model_config = ConfigDict(from_attributes=True)

class TaskCreate(BaseModel):
    name: str
    task_type: str = "instrument"
    requires_instrument: bool = True
    requires_human: bool = True
    est_duration_hours: Optional[float] = None
    switchover_hours: float = 0
    allow_split: bool = False
    allow_transfer: bool = False
    milestone_id: Optional[int] = None
    priority_weight: float = 1.0
    predecessor_ids: List[int] = []
    instrument_ids: List[int] = []
    assignee_id: Optional[int] = None
    parent_id: Optional[int] = None

class TaskOut(BaseModel):
    id: int
    project_id: int
    name: str
    task_type: str
    requires_instrument: bool
    requires_human: bool
    est_duration_hours: Optional[float]
    switchover_hours: float
    status: str
    earliest_start: Optional[datetime]
    latest_due: Optional[datetime]
    priority_weight: float
    instrument_ids: List[int] = []
    predecessor_ids: List[int] = []
    assignee_id: Optional[int] = None
    assignee_name: Optional[str] = None
    project_id: Optional[int] = None
    delay_hours: Optional[float] = None
    delay_reason: Optional[str] = None
    delay_reported_at: Optional[datetime] = None
    parent_id: Optional[int] = None
    children: List["TaskOut"] = []
    model_config = ConfigDict(from_attributes=True)

class ProjectCreate(BaseModel):
    name: str
    code: str
    client_name: Optional[str] = None
    priority: int = 0
    sla_level: Optional[str] = None
    profit_weight: float = 1.0
    manager_id: Optional[int] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class ProjectOut(BaseModel):
    id: int
    name: str
    code: str
    client_name: Optional[str]
    priority: int
    sla_level: Optional[str]
    status: str
    profit_weight: float
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    tasks: List[TaskOut] = []
    model_config = ConfigDict(from_attributes=True)

# ---- Instrument ----
class CapabilityCreate(BaseModel):
    tag_name: str
    tag_value: str

class CapabilityOut(BaseModel):
    id: int
    tag_name: str
    tag_value: str
    model_config = ConfigDict(from_attributes=True)

class MaintenanceCreate(BaseModel):
    start_time: datetime
    end_time: datetime
    mw_type: str
    description: Optional[str] = None

class MaintenanceOut(BaseModel):
    id: int
    instrument_id: Optional[int] = None
    start_time: datetime
    end_time: datetime
    mw_type: str
    description: Optional[str]
    model_config = ConfigDict(from_attributes=True)

class FaultCreate(BaseModel):
    description: str
    estimated_resolved_at: datetime
    resolved_at: Optional[datetime] = None

class FaultOut(BaseModel):
    id: int
    instrument_id: Optional[int] = None
    reported_at: datetime
    estimated_resolved_at: Optional[datetime] = None
    resolved_at: Optional[datetime]
    description: str
    status: str
    schedule_impact: Optional[dict] = None
    affected_tasks: List[dict] = []
    model_config = ConfigDict(from_attributes=True)

class InstrumentCreate(BaseModel):
    code: str
    name: str
    instrument_group: str = "GTI_Group"
    brand: Optional[str] = None
    model: Optional[str] = None
    location: Optional[str] = None
    availability_status: str = "available"
    buffer_rate: float = 1.1
    switchover_base_hours: float = 0.5
    capabilities: List[CapabilityCreate] = []

class InstrumentOut(BaseModel):
    id: int
    code: str
    name: str
    instrument_group: str
    brand: Optional[str]
    model: Optional[str]
    location: Optional[str]
    availability_status: str = "available"
    status: str
    buffer_rate: float
    switchover_base_hours: float
    capabilities: List[CapabilityOut] = []
    model_config = ConfigDict(from_attributes=True)

# ---- TimeSlot ----
class TimeSlotOut(BaseModel):
    id: int
    task_id: int
    instrument_id: Optional[int] = None
    plan_start: datetime
    plan_end: datetime
    actual_start: Optional[datetime]
    actual_end: Optional[datetime]
    tier: str
    status: str
    task_name: Optional[str] = None
    task_type: Optional[str] = None
    project_code: Optional[str] = None
    project_name: Optional[str] = None
    instrument_name: Optional[str] = None
    assignee_name: Optional[str] = None
    project_id: Optional[int] = None
    delay_hours: Optional[float] = None
    delay_reason: Optional[str] = None
    delay_reported_at: Optional[datetime] = None
    parent_id: Optional[int] = None
    children: List["TaskOut"] = []
    model_config = ConfigDict(from_attributes=True)

class TimeSlotUpdate(BaseModel):
    plan_start: Optional[datetime] = None
    plan_end: Optional[datetime] = None
    instrument_id: Optional[int] = None
    tier: Optional[str] = None

class TaskStatusUpdate(BaseModel):
    status: str
    actual_time: Optional[datetime] = None

# ---- Schedule ----
class ScheduleGenerateRequest(BaseModel):
    project_ids: Optional[List[int]] = None

class InsertOrderRequest(BaseModel):
    project_id: int
    task_ids: List[int]
    priority_override: Optional[int] = None

class InsertOrderCost(BaseModel):
    displaced_tasks: List[dict] = []
    affected_projects: List[dict] = []
    milestone_violations: List[dict] = []
    total_delay_hours: float = 0

class RescheduleRequest(BaseModel):
    trigger_type: str
    affected_task_id: Optional[int] = None
    affected_instrument_id: Optional[int] = None
    strategy: str = "local"
    description: Optional[str] = None

class TaskDelayRequest(BaseModel):
    delay_hours: float
    reason: str

class TaskDelayResponse(BaseModel):
    status: str
    task_id: int
    slot_id: int
    delay_hours: float
    shifted_slots: int
    affected_tasks: int
    reason: str

class NightRunRequest(BaseModel):
    duration_hours: float = Field(gt=0)
    earliest_start: Optional[str] = None
    latest_end: Optional[str] = None
    requires_operator: bool = False
    remark: Optional[str] = None

# ---- Stats ----
class UtilizationStats(BaseModel):
    instrument_id: Optional[int] = None
    instrument_name: str
    instrument_code: Optional[str] = None
    total_available_hours: float
    scheduled_hours: float
    actual_run_hours: float
    expected_utilization_rate: float
    actual_utilization_rate: float
    utilization_rate: float
    buffer_consumed_rate: float

class DashboardData(BaseModel):
    total_instruments: int
    active_instruments: int
    total_projects: int
    active_projects: int
    avg_utilization: float
    delayed_tasks: int
    buffer_warnings: List[str] = []
    milestone_risks: List[dict] = []

# ---- Notification ----

# ---- Schedule Rule ----

# ---- User ----
class UserCreate(BaseModel):
    username: str
    display_name: str
    password: Optional[str] = None
    role: str = "分析员"
    email: Optional[str] = None
    phone: Optional[str] = None
    wecom_id: Optional[str] = None
    is_active: bool = True

class UserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    email: Optional[str]
    phone: Optional[str]
    wecom_id: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ScheduleRuleOut(BaseModel):
    id: int
    category: str
    name: str
    code: str
    description: Optional[str]
    params: Optional[dict]
    is_enabled: bool
    sort_order: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class ScheduleRuleUpdate(BaseModel):
    params: Optional[dict] = None
    is_enabled: Optional[bool] = None
    sort_order: Optional[int] = None

class NotificationOut(BaseModel):
    id: int
    user_name: str
    n_type: str
    channel: str = "site"
    delivery_status: str = "success"
    error_message: Optional[str] = None
    title: Optional[str]
    content: Optional[str]
    is_read: bool
    is_confirmed: Optional[bool]
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)




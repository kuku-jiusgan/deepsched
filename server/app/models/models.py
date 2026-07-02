from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base

class Project(Base):
    __tablename__ = "project"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    client_name = Column(String(200))
    priority = Column(Integer, default=0)
    sla_level = Column(String(20))
    status = Column(String(20), default="active")
    profit_weight = Column(Float, default=1.0)
    manager = Column(String(100))
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    milestones = relationship("Milestone", back_populates="project", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")

class Milestone(Base):
    __tablename__ = "milestone"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    name = Column(String(200), nullable=False)
    due_date = Column(DateTime, nullable=False)
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.now)

    project = relationship("Project", back_populates="milestones")

class Task(Base):
    __tablename__ = "task"
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("project.id"), nullable=False)
    name = Column(String(300), nullable=False)
    task_type = Column(String(20), nullable=False)
    requires_instrument = Column(Boolean, default=False)
    requires_human = Column(Boolean, default=True)
    est_duration_hours = Column(Float)
    switchover_hours = Column(Float, default=0)
    allow_split = Column(Boolean, default=False)
    allow_transfer = Column(Boolean, default=False)
    milestone_id = Column(Integer, ForeignKey("milestone.id"))
    priority_weight = Column(Float, default=1.0)
    status = Column(String(20), default="pending")
    assignee_id = Column(Integer, ForeignKey("user.id"))
    assignee = relationship("User")
    earliest_start = Column(DateTime)
    latest_due = Column(DateTime)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    project = relationship("Project", back_populates="tasks")
    milestone = relationship("Milestone")

    @property
    def assignee_name(self):
        return self.assignee.display_name if self.assignee else None
    predecessors = relationship("TaskDependency", foreign_keys="TaskDependency.task_id", back_populates="task", cascade="all, delete-orphan")
    capability_requirements = relationship("TaskCapabilityRequirement", back_populates="task", cascade="all, delete-orphan")
    time_slots = relationship("TimeSlot", back_populates="task", cascade="all, delete-orphan")

class TaskDependency(Base):
    __tablename__ = "task_dependency"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False)
    predecessor_id = Column(Integer, ForeignKey("task.id"), nullable=False)
    __table_args__ = (UniqueConstraint("task_id", "predecessor_id"),)

    task = relationship("Task", foreign_keys=[task_id], back_populates="predecessors")
    predecessor = relationship("Task", foreign_keys=[predecessor_id])

class TaskCapabilityRequirement(Base):
    __tablename__ = "task_capability_requirement"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False)
    tag_name = Column(String(100), nullable=False)
    tag_value = Column(String(200), nullable=False)

    task = relationship("Task", back_populates="capability_requirements")

class Instrument(Base):
    __tablename__ = "instrument"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    instrument_group = Column(String(50), default="GTI_Group")
    brand = Column(String(50))
    model = Column(String(100))
    location = Column(String(50))
    status = Column(String(20), default="idle")
    buffer_rate = Column(Float, default=1.1)
    switchover_base_hours = Column(Float, default=0.5)
    label_x = Column(Integer, default=0)
    label_y = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)

    capabilities = relationship("InstrumentCapability", back_populates="instrument", cascade="all, delete-orphan")
    maintenance_windows = relationship("MaintenanceWindow", back_populates="instrument", cascade="all, delete-orphan")
    faults = relationship("InstrumentFault", back_populates="instrument", cascade="all, delete-orphan")
    time_slots = relationship("TimeSlot", back_populates="instrument", cascade="all, delete-orphan")

class InstrumentCapability(Base):
    __tablename__ = "instrument_capability"
    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(Integer, ForeignKey("instrument.id"), nullable=False)
    tag_name = Column(String(100), nullable=False)
    tag_value = Column(String(200), nullable=False)

    instrument = relationship("Instrument", back_populates="capabilities")

class MaintenanceWindow(Base):
    __tablename__ = "maintenance_window"
    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(Integer, ForeignKey("instrument.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    mw_type = Column(String(30), nullable=False)
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)

    instrument = relationship("Instrument", back_populates="maintenance_windows")

class InstrumentFault(Base):
    __tablename__ = "instrument_fault"
    id = Column(Integer, primary_key=True, autoincrement=True)
    instrument_id = Column(Integer, ForeignKey("instrument.id"), nullable=False)
    reported_at = Column(DateTime, default=datetime.now)
    resolved_at = Column(DateTime)
    description = Column(Text)
    status = Column(String(20), default="open")

    instrument = relationship("Instrument", back_populates="faults")

class TimeSlot(Base):
    __tablename__ = "time_slot"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("task.id"), nullable=False)
    instrument_id = Column(Integer, ForeignKey("instrument.id"), nullable=False)
    plan_start = Column(DateTime, nullable=False)
    plan_end = Column(DateTime, nullable=False)
    actual_start = Column(DateTime)
    actual_end = Column(DateTime)
    tier = Column(String(10), nullable=False, default="forecast")
    status = Column(String(20), default="scheduled")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    task = relationship("Task", back_populates="time_slots")
    instrument = relationship("Instrument", back_populates="time_slots")

class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(Integer)
    detail = Column(JSON)
    created_at = Column(DateTime, default=datetime.now)



class User(Base):
    __tablename__ = "user"
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    role = Column(String(30), nullable=False, comment="系统管理员/项目管理员/项目负责人/分析员")
    email = Column(String(100))
    phone = Column(String(20))
    password_hash = Column(String(128))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class ScheduleRule(Base):
    __tablename__ = "schedule_rule"
    id = Column(Integer, primary_key=True, autoincrement=True)
    category = Column(String(30), nullable=False, comment="决策变量/约束条件/目标函数")
    name = Column(String(100), nullable=False)
    code = Column(String(50), unique=True, nullable=False)
    description = Column(Text)
    params = Column(JSON, comment="可配置参数")
    is_enabled = Column(Boolean, default=True)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class Notification(Base):
    __tablename__ = "notification"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_name = Column(String(100), nullable=False)
    n_type = Column(String(30), nullable=False)
    title = Column(String(300))
    content = Column(Text)
    related_entity_type = Column(String(50))
    related_entity_id = Column(Integer)
    is_read = Column(Boolean, default=False)
    is_confirmed = Column(Boolean)
    created_at = Column(DateTime, default=datetime.now)

class TaskTypeConfig(Base):
    __tablename__ = "task_type_config"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="任务类型名称")
    code = Column(String(50), unique=True, nullable=False, comment="类型编码")
    resource_type = Column(String(20), nullable=False, default="both", comment="资源依赖: instrument/human/both")
    description = Column(Text, comment="描述")
    is_active = Column(Boolean, default=True, comment="是否启用")
    sort_order = Column(Integer, default=0, comment="排序")
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)


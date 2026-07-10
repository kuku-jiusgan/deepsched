from __future__ import annotations

from app.models import Project, Task, TaskDependency, TimeSlot
from app.schemas.schemas import ProjectCreate, TaskUpdate


SCHEDULE_FIELDS = {
    "task_type",
    "requires_instrument",
    "requires_human",
    "est_duration_hours",
    "switchover_hours",
    "allow_split",
    "allow_transfer",
    "milestone_id",
    "priority_weight",
    "predecessor_ids",
    "instrument_ids",
    "parent_id",
}
PROTECTED_TASK_STATUSES = {"running", "done", "completed"}


class PlanChangeNotFoundError(Exception):
    pass


class PlanChangeInvalidError(Exception):
    pass


def update_project_plan(db, project_id: int, data: ProjectCreate) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise PlanChangeNotFoundError("项目不存在")

    schedule_changed = any((
        project.priority != data.priority,
        project.start_date != data.start_date,
        project.end_date != data.end_date,
    ))
    if schedule_changed:
        _ensure_project_window_keeps_protected_slots(db, project_id, data)

    project.name = data.name
    project.code = data.code
    project.client_name = data.client_name
    project.priority = data.priority
    project.manager_id = data.manager_id
    project.start_date = data.start_date
    project.end_date = data.end_date
    if schedule_changed:
        _mark_project_movable_tasks_dirty(db, project_id)

    db.commit()
    db.refresh(project)
    return project


def update_task_plan(db, task_id: int, data: TaskUpdate) -> Task:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise PlanChangeNotFoundError("任务不存在")

    changes = data.model_dump(exclude_unset=True)
    predecessor_ids = changes.pop("predecessor_ids", None)
    instrument_ids = changes.get("instrument_ids")
    if "name" in changes and not changes["name"]:
        raise PlanChangeInvalidError("任务名称不能为空")
    if predecessor_ids is not None and task.id in predecessor_ids:
        raise PlanChangeInvalidError("任务不能依赖自身")
    schedule_changed = _has_schedule_changes(task, changes, predecessor_ids)
    is_structure_change = "parent_id" in changes and task.parent_id != changes["parent_id"]

    if schedule_changed:
        _ensure_schedule_fields_editable(db, task, is_structure_change)

    for field_name, value in changes.items():
        setattr(task, field_name, value)
    if instrument_ids is not None:
        task.instrument_ids = list(instrument_ids)
    if predecessor_ids is not None:
        _replace_dependencies(db, task.id, predecessor_ids)

    if schedule_changed:
        if is_structure_change:
            _mark_project_movable_tasks_dirty(db, task.project_id)
        else:
            _mark_task_and_downstream_dirty(db, task)

    db.commit()
    db.refresh(task)
    return task


def _has_schedule_changes(task: Task, changes: dict, predecessor_ids: list[int] | None) -> bool:
    for field_name in SCHEDULE_FIELDS - {"predecessor_ids"}:
        if field_name not in changes:
            continue
        old_value = getattr(task, field_name)
        new_value = changes[field_name]
        if field_name == "instrument_ids":
            if _normalized_ids(old_value) != _normalized_ids(new_value):
                return True
        elif old_value != new_value:
            return True
    if predecessor_ids is not None:
        return _normalized_ids(task.predecessor_ids) != _normalized_ids(predecessor_ids)
    return False


def _ensure_schedule_fields_editable(db, task: Task, is_structure_change: bool) -> None:
    if task.schedule_lock_status != "none":
        raise PlanChangeInvalidError(
            f"任务【{task.name}】已{_lock_label(task.schedule_lock_status)}，只能修改名称和负责人"
        )
    affected = _project_tasks(db, task.project_id) if is_structure_change else _downstream_tasks(db, task)
    protected = [item for item in affected if item.id != task.id and item.schedule_lock_status != "none"]
    if protected:
        names = "、".join(item.name for item in protected[:3])
        raise PlanChangeInvalidError(f"下游存在固定任务【{names}】，不能修改当前任务的排程字段")


def _ensure_project_window_keeps_protected_slots(db, project_id: int, data: ProjectCreate) -> None:
    tasks = _project_tasks(db, project_id)
    protected_ids = {task.id for task in tasks if task.schedule_lock_status != "none"}
    if not protected_ids:
        return
    slots = db.query(TimeSlot).filter(TimeSlot.task_id.in_(protected_ids)).all()
    for slot in slots:
        if data.start_date and slot.plan_start < data.start_date:
            raise PlanChangeInvalidError(f"项目开始时间晚于固定任务【{slot.task.name}】的排程时间")
        if data.end_date and slot.plan_end > data.end_date:
            raise PlanChangeInvalidError(f"项目结束时间早于固定任务【{slot.task.name}】的排程时间")


def _mark_task_and_downstream_dirty(db, task: Task) -> None:
    for affected_task in _downstream_tasks(db, task):
        if affected_task.schedule_lock_status == "none":
            affected_task.schedule_dirty = True


def _mark_project_movable_tasks_dirty(db, project_id: int) -> None:
    for task in _project_tasks(db, project_id):
        if task.schedule_lock_status == "none":
            task.schedule_dirty = True


def _downstream_tasks(db, task: Task) -> list[Task]:
    tasks = _project_tasks(db, task.project_id)
    task_by_id = {item.id: item for item in tasks}
    downstream_by_predecessor: dict[int, set[int]] = {}
    dependencies = db.query(TaskDependency).filter(
        TaskDependency.task_id.in_(task_by_id),
    ).all()
    for dependency in dependencies:
        downstream_by_predecessor.setdefault(dependency.predecessor_id, set()).add(dependency.task_id)

    affected_ids = {task.id}
    pending_ids = [task.id]
    while pending_ids:
        predecessor_id = pending_ids.pop()
        for downstream_id in downstream_by_predecessor.get(predecessor_id, set()):
            if downstream_id not in affected_ids:
                affected_ids.add(downstream_id)
                pending_ids.append(downstream_id)
    return [task_by_id[task_id] for task_id in affected_ids if task_id in task_by_id]


def _replace_dependencies(db, task_id: int, predecessor_ids: list[int]) -> None:
    db.query(TaskDependency).filter(TaskDependency.task_id == task_id).delete()
    for predecessor_id in sorted(set(predecessor_ids)):
        db.add(TaskDependency(task_id=task_id, predecessor_id=predecessor_id))


def _project_tasks(db, project_id: int) -> list[Task]:
    return db.query(Task).filter(Task.project_id == project_id).all()


def _normalized_ids(values) -> tuple[int, ...]:
    return tuple(sorted(int(value) for value in (values or [])))


def _lock_label(lock_status: str) -> str:
    return {"frozen": "冻结", "running": "开始运行", "completed": "完成"}.get(lock_status, "锁定")
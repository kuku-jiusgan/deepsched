from __future__ import annotations

from app.models import AuditLog, Project, Task, TaskDependency, TaskTypeConfig, User
from app.schemas.project_plan_draft_schemas import (
    ProjectPlanDraftCommitIn,
    ProjectPlanDraftCommitOut,
    ProjectPlanDraftIdMap,
)
from app.services.project_access_service import FULL_PROJECT_ACCESS_ROLES
from app.services.project_hours_validation_service import ProjectHoursExceededError, validate_project_estimated_hours
from app.services.project_instrument_validation_service import RequiredInstrumentError, validate_required_task_instruments
from app.services.project_task_rollup_service import recalculate_project_parent_hours
from app.services.user_role_service import has_any_role


class ProjectPlanDraftNotFoundError(Exception):
    pass


class ProjectPlanDraftPermissionError(Exception):
    pass


class ProjectPlanDraftInvalidError(Exception):
    pass


def commit_project_plan_drafts(
    db,
    project_id: int,
    data: ProjectPlanDraftCommitIn,
    user: User,
) -> ProjectPlanDraftCommitOut:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ProjectPlanDraftNotFoundError("项目不存在")
    if not has_any_role(user, FULL_PROJECT_ACCESS_ROLES) and project.manager_id != user.id:
        raise ProjectPlanDraftPermissionError("无权保存该项目计划")
    client_ids = [item.client_id for item in data.tasks]
    if len(client_ids) != len(set(client_ids)):
        raise ProjectPlanDraftInvalidError("草稿任务标识重复")
    _validate_task_types(db, data)
    _validate_references(db, project_id, data)
    try:
        validate_required_task_instruments(data.tasks)
    except RequiredInstrumentError as exc:
        raise ProjectPlanDraftInvalidError(str(exc))

    id_map: dict[int, int] = {}
    created_by_client_id: dict[int, Task] = {}
    parent_client_ids = {
        item.parent_id for item in data.tasks if item.parent_id is not None
    }
    for item in data.tasks:
        is_parent = item.client_id in parent_client_ids and not item.is_external_gate
        task = Task(
            project_id=project_id,
            name=item.name.strip(),
            task_type=(
                "approval_gate" if item.is_external_gate
                else "group" if is_parent
                else item.task_type
            ),
            requires_instrument=(
                False if item.is_external_gate or is_parent
                else item.requires_instrument
            ),
            requires_human=(
                False if item.is_external_gate or is_parent
                else item.requires_human
            ),
            est_duration_hours=(
                None if item.is_external_gate or is_parent
                else item.estimated_hours
            ),
            switchover_hours=(
                0 if item.is_external_gate or is_parent
                else item.switchover_hours
            ),
            assignee_id=(
                project.manager_id if item.is_external_gate
                else None if is_parent
                else item.assignee_id
            ),
            parent_id=None,
            plan_order=item.plan_order,
            instrument_ids=(
                [] if item.is_external_gate or is_parent
                else item.instrument_ids
            ),
            is_external_gate=item.is_external_gate,
            gate_status="not_submitted" if item.is_external_gate else None,
            status="waiting_external" if item.is_external_gate else "pending",
            schedule_dirty=not item.is_external_gate and not is_parent,
        )
        db.add(task)
        db.flush()
        id_map[item.client_id] = task.id
        created_by_client_id[item.client_id] = task

    for item in data.tasks:
        task = created_by_client_id[item.client_id]
        task.parent_id = _resolve_id(item.parent_id, id_map)
        for predecessor_id in sorted(set(item.predecessor_ids)):
            db.add(TaskDependency(
                task_id=task.id,
                predecessor_id=_resolve_id(predecessor_id, id_map),
            ))
    db.flush()
    for item in data.tasks:
        if not item.is_external_gate:
            continue
        gate_id = id_map[item.client_id]
        for task in _downstream_tasks(db, gate_id):
            if task.schedule_lock_status == "none":
                task.status = "waiting_external"
                task.schedule_dirty = False

    try:
        recalculate_project_parent_hours(db, project_id)
        validate_project_estimated_hours(db, project_id)
    except ProjectHoursExceededError as exc:
        db.rollback()
        raise ProjectPlanDraftInvalidError(str(exc))
    db.add(AuditLog(
        user_name=user.display_name or user.username,
        action="project_plan_drafts_committed",
        target_type="project",
        target_id=project_id,
        detail={"created": len(data.tasks), "client_ids": client_ids},
    ))
    db.commit()
    return ProjectPlanDraftCommitOut(
        status="ok",
        message=f"已保存 {len(data.tasks)} 个计划节点",
        created=len(data.tasks),
        id_map=[
            ProjectPlanDraftIdMap(client_id=client_id, task_id=task_id)
            for client_id, task_id in id_map.items()
        ],
    )


def _validate_task_types(db, data: ProjectPlanDraftCommitIn) -> None:
    parent_client_ids = {
        item.parent_id for item in data.tasks if item.parent_id is not None
    }
    codes = {
        item.task_type
        for item in data.tasks
        if item.client_id not in parent_client_ids
        and not item.is_external_gate
        and item.task_type != "group"
    }
    active_codes = {
        item.code for item in db.query(TaskTypeConfig).filter(
            TaskTypeConfig.code.in_(codes), TaskTypeConfig.is_active.is_(True)
        ).all()
    }
    missing = codes - active_codes
    if missing:
        raise ProjectPlanDraftInvalidError(f"任务类型未启用：{', '.join(sorted(missing))}")


def _validate_references(db, project_id: int, data: ProjectPlanDraftCommitIn) -> None:
    client_ids = {item.client_id for item in data.tasks}
    referenced_ids = {
        reference_id
        for item in data.tasks
        for reference_id in [item.parent_id, *item.predecessor_ids]
        if reference_id is not None
    }
    missing_client_ids = {item_id for item_id in referenced_ids if item_id < 0} - client_ids
    if missing_client_ids:
        raise ProjectPlanDraftInvalidError("草稿引用了不存在的临时任务")
    existing_ids = {item_id for item_id in referenced_ids if item_id > 0}
    if existing_ids:
        valid_existing = {
            row[0] for row in db.query(Task.id).filter(
                Task.project_id == project_id, Task.id.in_(existing_ids)
            ).all()
        }
        if valid_existing != existing_ids:
            raise ProjectPlanDraftInvalidError("草稿引用了其他项目的任务")


def _resolve_id(value: int | None, id_map: dict[int, int]) -> int | None:
    if value is None or value > 0:
        return value
    return id_map[value]


def _downstream_tasks(db, predecessor_id: int) -> list[Task]:
    dependencies = db.query(TaskDependency).all()
    by_predecessor: dict[int, set[int]] = {}
    for dependency in dependencies:
        by_predecessor.setdefault(dependency.predecessor_id, set()).add(dependency.task_id)
    task_ids: set[int] = set()
    pending = [predecessor_id]
    while pending:
        current = pending.pop()
        for task_id in by_predecessor.get(current, set()):
            if task_id not in task_ids:
                task_ids.add(task_id)
                pending.append(task_id)
    return db.query(Task).filter(Task.id.in_(task_ids)).all() if task_ids else []

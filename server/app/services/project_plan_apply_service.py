from __future__ import annotations

import hashlib
import json
from datetime import datetime

from app.models import Project, Task, TaskDependency, TimeSlot
from app.schemas.schemas import (
    InsertOrderImpact,
    ProjectPlanApplyResponse,
    ProjectPlanInsertConfirmRequest,
)
from app.services.schedule_insert_service import (
    _build_impacts,
    _load_lower_priority_movable_tasks,
    _selected_instrument_ids,
    _task_windows,
)


MOVABLE_TIERS = ["confirmed", "forecast"]
MOVABLE_SLOT_STATUSES = ["scheduled", "blocked"]


class ProjectPlanNotFoundError(Exception):
    pass


class ProjectPlanInvalidError(Exception):
    pass


def apply_project_plan(db, project_id: int) -> ProjectPlanApplyResponse:
    project, selected_tasks = _load_project_candidates(db, project_id)
    if not selected_tasks:
        return ProjectPlanApplyResponse(
            status="no_changes",
            message="当前项目没有需要重新排程的任务",
            project_id=project_id,
        )

    stable_result = _execute_replan(db, project, selected_tasks, [], commit=True)
    if stable_result.status == "applied":
        return stable_result
    db.rollback()

    try:
        return _preview_plan_insert(db, project, selected_tasks, stable_result.message)
    finally:
        db.rollback()


def confirm_project_plan_insert(
    db,
    data: ProjectPlanInsertConfirmRequest,
) -> ProjectPlanApplyResponse:
    project, selected_tasks = _load_project_candidates(db, data.project_id)
    if not selected_tasks:
        raise ProjectPlanInvalidError("计划已经更新，请重新计算排程")
    movable_tasks = _load_insert_movable_tasks(db, project, selected_tasks)
    if not movable_tasks:
        raise ProjectPlanInvalidError("当前没有允许移动的低优先级任务")
    preview_token = _plan_fingerprint(db, project, selected_tasks + movable_tasks)
    if preview_token != data.preview_token:
        raise ProjectPlanInvalidError("计划或排程数据已变化，请重新计算影响")
    result = _execute_replan(db, project, selected_tasks, movable_tasks, commit=True)
    if result.status != "applied":
        db.rollback()
        raise ProjectPlanInvalidError(result.message or "插单排程失败")
    return result


def _preview_plan_insert(
    db,
    project: Project,
    selected_tasks: list[Task],
    stable_message: str | None,
) -> ProjectPlanApplyResponse:
    movable_tasks = _load_insert_movable_tasks(db, project, selected_tasks)
    if not movable_tasks:
        return ProjectPlanApplyResponse(
            status="error",
            message=stable_message or "没有可移动的低优先级任务，无法完成重排",
            project_id=project.id,
        )
    preview_token = _plan_fingerprint(db, project, selected_tasks + movable_tasks)
    preview = _execute_replan(db, project, selected_tasks, movable_tasks, commit=False)
    if preview.status != "applied":
        return ProjectPlanApplyResponse(
            status="error",
            message=preview.message or stable_message or "插单模拟失败",
            project_id=project.id,
        )
    return ProjectPlanApplyResponse(
        status="insert_confirmation_required",
        message="稳定重排不可行，需要移动低优先级任务，请确认插单影响",
        project_id=project.id,
        schedule_run_id=preview.schedule_run_id,
        timeslots_created=preview.timeslots_created,
        moved_tasks=preview.moved_tasks,
        conflicts_checked=preview.conflicts_checked,
        preview_token=preview_token,
        impacts=preview.impacts,
    )


def _execute_replan(
    db,
    project: Project,
    selected_tasks: list[Task],
    movable_tasks: list[Task],
    commit: bool,
) -> ProjectPlanApplyResponse:
    replan_tasks = _unique_tasks(selected_tasks + movable_tasks)
    replan_task_ids = {task.id for task in replan_tasks}
    selected_task_ids = {task.id for task in selected_tasks}
    old_windows = _task_windows(db, replan_task_ids)

    _delete_movable_slots(db, replan_task_ids)
    for task in replan_tasks:
        task.status = "pending"
    db.flush()

    from app.services.scheduler import SchedulerService

    solver_result = SchedulerService(db).generate(
        task_ids=sorted(replan_task_ids),
        mode="insert" if movable_tasks else "normal",
        commit=False,
    )
    if solver_result.get("status") != "ok":
        db.rollback()
        return ProjectPlanApplyResponse(
            status="error",
            message=solver_result.get("message") or "排程失败",
            project_id=project.id,
        )

    schedule_run_id = str(solver_result.get("schedule_run_id") or "")
    new_windows = _task_windows(db, replan_task_ids, schedule_run_id)
    impacts = _build_impacts(replan_tasks, selected_task_ids, old_windows, new_windows)
    for task in db.query(Task).filter(Task.project_id == project.id).all():
        task.schedule_dirty = False

    response = ProjectPlanApplyResponse(
        status="applied",
        message=f"排程完成，创建 {int(solver_result.get('timeslots_created', 0))} 个时间槽",
        project_id=project.id,
        schedule_run_id=schedule_run_id,
        timeslots_created=int(solver_result.get("timeslots_created", 0)),
        moved_tasks=sum(1 for impact in impacts if not impact.is_insert_task),
        conflicts_checked=True,
        impacts=impacts,
    )
    if commit:
        db.commit()
    else:
        db.flush()
    return response


def _load_project_candidates(db, project_id: int) -> tuple[Project, list[Task]]:
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise ProjectPlanNotFoundError("项目不存在")
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    parent_ids = {task.parent_id for task in tasks if task.parent_id is not None}
    task_by_id = {task.id: task for task in tasks}
    seed_ids = {
        task.id for task in tasks
        if task.schedule_dirty or task.status in {"pending", "ready"}
    }
    affected_ids = _downstream_ids(db, seed_ids, set(task_by_id))
    candidates = [
        task for task in tasks
        if task.id in affected_ids
        and task.id not in parent_ids
        and task.schedule_lock_status == "none"
    ]
    return project, sorted(candidates, key=lambda task: (task.created_at, task.id))


def _load_insert_movable_tasks(db, project: Project, selected_tasks: list[Task]) -> list[Task]:
    selected_ids = {task.id for task in selected_tasks}
    movable = _load_lower_priority_movable_tasks(
        db,
        int(project.priority or 3),
        selected_ids,
        _selected_instrument_ids(selected_tasks),
    )
    return _unique_tasks(movable)


def _delete_movable_slots(db, task_ids: set[int]) -> None:
    db.query(TimeSlot).filter(
        TimeSlot.task_id.in_(task_ids),
        TimeSlot.tier.in_(MOVABLE_TIERS),
        TimeSlot.status.in_(MOVABLE_SLOT_STATUSES),
        TimeSlot.actual_start.is_(None),
    ).delete(synchronize_session=False)


def _downstream_ids(db, seed_ids: set[int], project_task_ids: set[int]) -> set[int]:
    if not seed_ids:
        return set()
    dependencies = db.query(TaskDependency).filter(
        TaskDependency.task_id.in_(project_task_ids),
    ).all()
    downstream_by_predecessor: dict[int, set[int]] = {}
    for dependency in dependencies:
        downstream_by_predecessor.setdefault(dependency.predecessor_id, set()).add(dependency.task_id)
    affected_ids = set(seed_ids)
    pending_ids = list(seed_ids)
    while pending_ids:
        predecessor_id = pending_ids.pop()
        for downstream_id in downstream_by_predecessor.get(predecessor_id, set()):
            if downstream_id not in affected_ids:
                affected_ids.add(downstream_id)
                pending_ids.append(downstream_id)
    return affected_ids


def _plan_fingerprint(db, project: Project, tasks: list[Task]) -> str:
    unique_tasks = _unique_tasks(tasks)
    slots = db.query(TimeSlot).filter(TimeSlot.status.in_(["scheduled", "running", "completed", "blocked", "interrupted"])).order_by(TimeSlot.id).all()
    payload = {
        "project": [
            project.id,
            project.priority,
            _iso(project.start_date),
            _iso(project.end_date),
            _iso(project.updated_at),
        ],
        "tasks": [
            [
                task.id,
                task.project_id,
                int(task.project.priority or 3) if task.project else 3,
                task.status,
                bool(task.schedule_dirty),
                task.task_type,
                task.est_duration_hours,
                task.switchover_hours,
                bool(task.allow_split),
                bool(task.allow_transfer),
                task.milestone_id,
                task.priority_weight,
                sorted(task.instrument_ids or []),
                sorted(task.predecessor_ids),
                task.parent_id,
                _iso(task.updated_at),
            ]
            for task in unique_tasks
        ],
        "slots": [
            [
                slot.id,
                slot.task_id,
                slot.instrument_id,
                _iso(slot.plan_start),
                _iso(slot.plan_end),
                slot.tier,
                slot.status,
                _iso(slot.updated_at),
            ]
            for slot in slots
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _unique_tasks(tasks: list[Task]) -> list[Task]:
    return sorted({task.id: task for task in tasks}.values(), key=lambda task: (task.project_id, task.created_at, task.id))


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None
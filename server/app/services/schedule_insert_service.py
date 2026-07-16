from __future__ import annotations

from datetime import datetime

from app.models import Project, Task, TimeSlot
from app.schemas.schemas import (
    InsertOrderImpact,
    InsertOrderPreview,
    InsertOrderRequest,
    InsertOrderResult,
)


class ScheduleInsertNotFoundError(Exception):
    pass


class ScheduleInsertInvalidError(Exception):
    pass


def preview_insert(db, data: InsertOrderRequest) -> InsertOrderPreview:
    preview = _execute_insert(db, data, commit=False)
    db.rollback()
    return preview


def confirm_insert(db, data: InsertOrderRequest) -> InsertOrderResult:
    preview = _execute_insert(db, data, commit=True)
    return InsertOrderResult(
        status="ok",
        schedule_run_id=preview.schedule_run_id,
        timeslots_created=preview.timeslots_created,
        moved_tasks=len(preview.impacts),
        conflicts_checked=True,
        impacts=preview.impacts,
    )


def _execute_insert(db, data: InsertOrderRequest, commit: bool) -> InsertOrderPreview:
    project = db.query(Project).filter(Project.id == data.project_id).first()
    if not project:
        raise ScheduleInsertNotFoundError("插单项目不存在")

    selected_tasks = db.query(Task).filter(Task.id.in_(data.task_ids)).all()
    if len(selected_tasks) != len(set(data.task_ids)):
        raise ScheduleInsertNotFoundError("插单任务不存在")
    if any(task.project_id != project.id for task in selected_tasks):
        raise ScheduleInsertInvalidError("插单任务必须属于所选项目")

    selected_task_ids = {task.id for task in selected_tasks}
    _ensure_selected_tasks_are_movable(db, selected_task_ids)
    insert_priority = data.priority_override if data.priority_override is not None else int(project.priority or 999)
    movable_tasks = _load_lower_priority_movable_tasks(
        db,
        insert_priority,
        selected_task_ids,
        _selected_instrument_ids(selected_tasks),
    )
    replan_tasks = selected_tasks + movable_tasks
    replan_task_ids = {task.id for task in replan_tasks}
    old_windows = _task_windows(db, replan_task_ids)

    db.query(TimeSlot).filter(
        TimeSlot.task_id.in_(replan_task_ids),
        TimeSlot.tier.in_(["confirmed", "forecast"]),
        TimeSlot.status.in_(["scheduled", "blocked"]),
    ).delete(synchronize_session=False)
    for task in replan_tasks:
        task.status = "pending"
    db.flush()

    from app.services.scheduler import SchedulerService

    result = SchedulerService(db).generate(
        task_ids=sorted(replan_task_ids),
        mode="insert",
        commit=False,
    )
    if result.get("status") != "ok":
        db.rollback()
        raise ScheduleInsertInvalidError(result.get("message") or "插单排程失败")

    schedule_run_id = result.get("schedule_run_id", "")
    new_windows = _task_windows(db, replan_task_ids, schedule_run_id)
    impacts = _build_impacts(replan_tasks, selected_task_ids, old_windows, new_windows)
    preview = InsertOrderPreview(
        status="ok",
        schedule_run_id=schedule_run_id,
        timeslots_created=int(result.get("timeslots_created", 0)),
        total_delay_hours=round(sum(max(0, impact.delay_hours) for impact in impacts), 1),
        impacts=impacts,
    )
    if commit:
        db.commit()
    return preview


def _ensure_selected_tasks_are_movable(db, task_ids: set[int]) -> None:
    protected_slot = db.query(TimeSlot).filter(
        TimeSlot.task_id.in_(task_ids),
        (
            (TimeSlot.tier == "frozen")
            | TimeSlot.status.in_(["running", "completed"])
            | TimeSlot.actual_start.isnot(None)
        ),
    ).first()
    if protected_slot:
        raise ScheduleInsertInvalidError("冻结、运行中或已完成的任务不能作为插单任务重新排程")


def _load_lower_priority_movable_tasks(
    db,
    insert_priority: int,
    excluded_task_ids: set[int],
    selected_instrument_ids: set[int],
    include_same_priority: bool = False,
    unstarted_projects_only: bool = False,
) -> list[Task]:
    priority_filter = (
        Project.priority >= insert_priority
        if include_same_priority
        else Project.priority > insert_priority
    )
    candidate_tasks = db.query(Task).join(Project).filter(
        priority_filter,
        Task.status == "scheduled",
        ~Task.id.in_(excluded_task_ids),
    ).order_by(Project.priority, Task.created_at, Task.id).all()
    movable = []
    for task in candidate_tasks:
        if unstarted_projects_only and _project_has_started(db, task.project_id):
            continue
        has_protected_slot = db.query(TimeSlot.id).filter(
            TimeSlot.task_id == task.id,
            (
                (TimeSlot.tier == "frozen")
                | TimeSlot.status.in_(["running", "completed"])
                | TimeSlot.actual_start.isnot(None)
            ),
        ).first()
        has_future_slot = db.query(TimeSlot.id).filter(
            TimeSlot.task_id == task.id,
            TimeSlot.tier.in_(["confirmed", "forecast"]),
            TimeSlot.status.in_(["scheduled", "blocked"]),
            TimeSlot.plan_start >= datetime.now(),
            *(
                [TimeSlot.instrument_id.in_(selected_instrument_ids)]
                if selected_instrument_ids
                else []
            ),
        ).first()
        if not has_protected_slot and has_future_slot:
            movable.append(task)
    return movable


def _project_has_started(db, project_id: int) -> bool:
    started_task = db.query(Task.id).filter(
        Task.project_id == project_id,
        Task.status.in_(["running", "completed", "done"]),
    ).first()
    if started_task:
        return True
    started_slot = db.query(TimeSlot.id).join(Task).filter(
        Task.project_id == project_id,
        (
            TimeSlot.actual_start.isnot(None)
            | TimeSlot.status.in_(["running", "completed"])
        ),
    ).first()
    return started_slot is not None


def _selected_instrument_ids(tasks: list[Task]) -> set[int]:
    instrument_ids = set()
    for task in tasks:
        raw_ids = task.instrument_ids or []
        if isinstance(raw_ids, list):
            instrument_ids.update(int(instrument_id) for instrument_id in raw_ids)
    return instrument_ids


def _task_windows(db, task_ids: set[int], schedule_run_id: str | None = None) -> dict[int, tuple[datetime, datetime]]:
    query = db.query(TimeSlot).filter(TimeSlot.task_id.in_(task_ids))
    if schedule_run_id:
        query = query.filter(TimeSlot.schedule_run_id == schedule_run_id)
    windows: dict[int, tuple[datetime, datetime]] = {}
    for slot in query.order_by(TimeSlot.plan_start, TimeSlot.id).all():
        if slot.task_id not in windows:
            windows[slot.task_id] = (slot.plan_start, slot.plan_end)
            continue
        start, end = windows[slot.task_id]
        windows[slot.task_id] = (min(start, slot.plan_start), max(end, slot.plan_end))
    return windows


def _build_impacts(
    tasks: list[Task],
    selected_task_ids: set[int],
    old_windows: dict[int, tuple[datetime, datetime]],
    new_windows: dict[int, tuple[datetime, datetime]],
) -> list[InsertOrderImpact]:
    impacts = []
    for task in tasks:
        new_window = new_windows.get(task.id)
        if not new_window:
            continue
        old_window = old_windows.get(task.id)
        delay_hours = 0.0
        if old_window:
            delay_hours = (new_window[1] - old_window[1]).total_seconds() / 3600
        impacts.append(InsertOrderImpact(
            task_id=task.id,
            task_name=task.name,
            project_id=task.project_id,
            project_name=task.project.name if task.project else "",
            is_insert_task=task.id in selected_task_ids,
            original_start=old_window[0] if old_window else None,
            original_end=old_window[1] if old_window else None,
            new_start=new_window[0],
            new_end=new_window[1],
            delay_hours=round(delay_hours, 1),
        ))
    return impacts

from app.models import Instrument, Milestone, Task, User


class ProjectReferenceInvalidError(Exception):
    pass


def validate_task_references(
    db,
    project_id: int,
    *,
    parent_id: int | None,
    milestone_id: int | None,
    predecessor_ids: list[int],
    assignee_id: int | None,
    instrument_ids: list[int],
) -> None:
    if parent_id is not None:
        _require_project_task(db, project_id, parent_id, "父任务")
    if milestone_id is not None:
        milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
        if milestone is None or milestone.project_id != project_id:
            raise ProjectReferenceInvalidError("里程碑不属于当前项目")
    for predecessor_id in set(predecessor_ids):
        _require_project_task(db, project_id, predecessor_id, "前置任务")
    if assignee_id is not None:
        assignee = db.query(User).filter(User.id == assignee_id, User.is_active.is_(True)).first()
        if assignee is None:
            raise ProjectReferenceInvalidError("任务负责人不存在或已停用")
    existing_instrument_ids = {
        row[0]
        for row in db.query(Instrument.id).filter(Instrument.id.in_(set(instrument_ids))).all()
    }
    if existing_instrument_ids != set(instrument_ids):
        raise ProjectReferenceInvalidError("任务引用了不存在的仪器")


def _require_project_task(db, project_id: int, task_id: int, label: str) -> None:
    task = db.query(Task).filter(Task.id == task_id).first()
    if task is None or task.project_id != project_id:
        raise ProjectReferenceInvalidError(f"{label}不属于当前项目")

from app.models import Task


class TaskReorderInvalidError(Exception):
    pass


def reorder_project_tasks(db, project_id: int, parent_id: int | None, task_ids: list[int]) -> None:
    query = db.query(Task).filter(Task.project_id == project_id)
    query = query.filter(Task.parent_id.is_(None)) if parent_id is None else query.filter(Task.parent_id == parent_id)
    siblings = query.all()
    if len(task_ids) != len(set(task_ids)) or set(task_ids) != {task.id for task in siblings}:
        raise TaskReorderInvalidError("任务排序范围不正确，请刷新后重试")
    task_by_id = {task.id: task for task in siblings}
    for index, task_id in enumerate(task_ids):
        task_by_id[task_id].plan_order = index
    db.commit()

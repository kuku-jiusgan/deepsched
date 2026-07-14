from app.models import Task


def recalculate_project_parent_hours(db, project_id: int) -> int:
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    task_by_id = {task.id: task for task in tasks}
    children_by_parent: dict[int, list[Task]] = {}
    for task in tasks:
        if task.parent_id in task_by_id:
            children_by_parent.setdefault(task.parent_id, []).append(task)

    totals: dict[int, float] = {}

    def task_hours(task: Task) -> float:
        if task.id in totals:
            return totals[task.id]
        children = children_by_parent.get(task.id, [])
        total = (
            sum(task_hours(child) for child in children)
            if children
            else float(task.est_duration_hours or 0)
        )
        totals[task.id] = total
        return total

    updated = 0
    for parent_id in children_by_parent:
        parent = task_by_id[parent_id]
        total = task_hours(parent)
        if parent.est_duration_hours != total:
            parent.est_duration_hours = total
            updated += 1
    return updated
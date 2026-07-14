from app.models import Project, Task


COMPLETED_TASK_STATUSES = {"done", "completed"}
NOT_STARTED_TASK_STATUSES = {"pending", "ready", "scheduled"}


def calculate_project_status(project: Project) -> str:
    tasks = _leaf_tasks(project.tasks or [])
    if not tasks:
        return "pending"
    if all(task.status in COMPLETED_TASK_STATUSES for task in tasks):
        return "completed"
    if all(task.status in NOT_STARTED_TASK_STATUSES for task in tasks):
        return "pending"
    return "active"


def _leaf_tasks(tasks: list[Task]) -> list[Task]:
    parent_ids = {task.parent_id for task in tasks if task.parent_id is not None}
    return [task for task in tasks if task.id not in parent_ids]

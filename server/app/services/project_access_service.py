from app.models import Project, Task


FULL_PROJECT_ACCESS_ROLES = {"系统管理员", "项目管理员", "分析所所长"}


class ProjectNotVisibleError(Exception):
    pass


def list_visible_projects(db, user) -> list[Project]:
    query = db.query(Project)
    if user.role not in FULL_PROJECT_ACCESS_ROLES:
        query = query.filter(Project.manager_id == user.id)
    return query.all()


def get_visible_project(db, project_id: int, user) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None or not can_view_project(project, user):
        raise ProjectNotVisibleError("项目不存在或无权查看")
    return project


def get_visible_project_dag(db, project_id: int, user) -> dict:
    get_visible_project(db, project_id, user)
    tasks = db.query(Task).filter(Task.project_id == project_id).all()
    return {
        "nodes": [
            {
                "id": task.id,
                "name": task.name,
                "type": task.task_type,
                "requires_instrument": task.requires_instrument,
                "status": task.status,
                "is_external_gate": bool(task.is_external_gate),
                "gate_status": task.gate_status,
            }
            for task in tasks
        ],
        "edges": [
            {"from": dependency.predecessor_id, "to": task.id}
            for task in tasks
            for dependency in task.predecessors
        ],
    }


def can_view_project(project: Project, user) -> bool:
    return (
        user.role in FULL_PROJECT_ACCESS_ROLES
        or project.manager_id == user.id
    )

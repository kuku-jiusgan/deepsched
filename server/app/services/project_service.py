from datetime import datetime

from app.models import Project
from app.schemas.schemas import ProjectCreate


class ProjectCodeExistsError(Exception):
    pass


def create_project(db, data: ProjectCreate) -> Project:
    project_code = data.code.strip()
    if db.query(Project).filter(Project.code == project_code).first():
        raise ProjectCodeExistsError(f"项目编号 {project_code} 已存在")

    project = Project(
        name=data.name.strip(),
        code=project_code,
        client_name=data.client_name,
        estimated_hours=data.estimated_hours,
        priority=data.priority,
        status="pending",
        manager_id=data.manager_id,
        start_date=_naive_datetime(data.start_date),
        end_date=_naive_datetime(data.end_date),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def _naive_datetime(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.replace(tzinfo=None)

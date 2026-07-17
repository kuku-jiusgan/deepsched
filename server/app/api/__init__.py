from fastapi import APIRouter, Depends

from app.api import (
    alert_rules,
    approval_gates,
    calendar_api,
    instruments,
    notifications,
    project_plan_drafts,
    project_plan_schedules,
    project_plan_templates,
    projects,
    schedule_rules,
    schedules,
    stats,
    task_types,
)
from app.api.users import require_authenticated_user


protected_router = APIRouter(dependencies=[Depends(require_authenticated_user)])

for router in (
    instruments.router,
    projects.router,
    schedules.router,
    project_plan_schedules.router,
    schedule_rules.router,
    stats.router,
    notifications.router,
    task_types.router,
    alert_rules.router,
    calendar_api.router,
    approval_gates.router,
    project_plan_templates.router,
    project_plan_drafts.router,
):
    protected_router.include_router(router)

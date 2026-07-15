from pydantic import BaseModel


class StandardPlanTaskOut(BaseModel):
    id: int
    name: str
    task_type: str
    percentage: float | None = None
    estimated_hours: float | None = None
    is_approval_restriction: bool = False


class StandardPlanImportOut(BaseModel):
    status: str
    message: str
    project_id: int
    estimated_hours: float
    tasks: list[StandardPlanTaskOut]


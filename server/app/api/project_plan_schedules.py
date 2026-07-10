from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.schemas import (
    ProjectPlanApplyRequest,
    ProjectPlanApplyResponse,
    ProjectPlanInsertConfirmRequest,
)
from app.services.project_plan_apply_service import (
    ProjectPlanInvalidError,
    ProjectPlanNotFoundError,
    apply_project_plan,
    confirm_project_plan_insert,
)

router = APIRouter(prefix="/api/v1/schedules", tags=["schedules"])


@router.post("/apply-project-plan", response_model=ProjectPlanApplyResponse)
def apply_saved_project_plan(data: ProjectPlanApplyRequest, db: Session = Depends(get_db)):
    try:
        return apply_project_plan(db, data.project_id)
    except ProjectPlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ProjectPlanInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/apply-project-plan/confirm-insert", response_model=ProjectPlanApplyResponse)
def confirm_saved_project_plan_insert(data: ProjectPlanInsertConfirmRequest, db: Session = Depends(get_db)):
    try:
        return confirm_project_plan_insert(db, data)
    except ProjectPlanNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ProjectPlanInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
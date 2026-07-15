from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.users import auth_token, get_current_user
from app.core.database import get_db
from app.schemas.project_plan_template_schemas import StandardPlanImportOut
from app.services.project_plan_template_service import (
    ProjectPlanTemplateInvalidError,
    ProjectPlanTemplateNotFoundError,
    ProjectPlanTemplatePermissionError,
    import_standard_plan,
)


router = APIRouter(prefix="/api/v1/projects", tags=["project-plan-templates"])


@router.post("/{project_id}/import-standard-plan", response_model=StandardPlanImportOut)
def import_project_plan(project_id: int, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    try:
        return import_standard_plan(db, project_id, get_current_user(token, db))
    except ProjectPlanTemplateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ProjectPlanTemplatePermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ProjectPlanTemplateInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


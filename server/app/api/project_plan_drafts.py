from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.users import auth_token, get_current_user
from app.core.database import get_db
from app.schemas.project_plan_draft_schemas import ProjectPlanDraftCommitIn, ProjectPlanDraftCommitOut
from app.services.project_plan_draft_service import (
    ProjectPlanDraftInvalidError,
    ProjectPlanDraftNotFoundError,
    ProjectPlanDraftPermissionError,
    commit_project_plan_drafts,
)


router = APIRouter(prefix="/api/v1/projects", tags=["project-plan-drafts"])


@router.post("/{project_id}/plan-drafts/commit", response_model=ProjectPlanDraftCommitOut)
def commit_drafts(project_id: int, data: ProjectPlanDraftCommitIn, token: str = Depends(auth_token), db: Session = Depends(get_db)):
    try:
        return commit_project_plan_drafts(db, project_id, data, get_current_user(token, db))
    except ProjectPlanDraftNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ProjectPlanDraftPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ProjectPlanDraftInvalidError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


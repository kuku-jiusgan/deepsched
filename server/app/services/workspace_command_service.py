from app.domain.errors import DomainNotFoundError, DomainValidationError
from app.repositories.workspace_repository import get_time_slot
from app.services.schedule_completion_service import complete_task_and_shift


def complete_workspace_task(db, slot_id: int, release_instrument: bool) -> dict:
    slot = get_time_slot(db, slot_id)
    if slot is None:
        raise DomainNotFoundError("时间槽不存在")
    result = complete_task_and_shift(
        db,
        slot.task_id,
        completed_slot_id=slot.id,
        release_instrument=release_instrument,
    )
    if result.get("status") == "error":
        raise DomainValidationError(result.get("message") or "任务完成失败")
    return result

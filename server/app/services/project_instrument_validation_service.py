from collections.abc import Iterable


REQUIRED_INSTRUMENT_TASK_TYPES = {"FFKF_001", "FFYZ_001"}


class RequiredInstrumentError(Exception):
    pass


def validate_required_task_instruments(tasks: Iterable[object]) -> None:
    missing_names = [
        str(task.name)
        for task in tasks
        if getattr(task, "task_type", None) in REQUIRED_INSTRUMENT_TASK_TYPES
        and not getattr(task, "is_external_gate", False)
        and not list(getattr(task, "instrument_ids", None) or [])
    ]
    if missing_names:
        raise RequiredInstrumentError(
            f"任务【{'、'.join(missing_names)}】必须指定仪器后才能保存并开始排程"
        )

DELAYED_STATUS = "delayed"
NOT_DELAYED_STATUS = "not_delayed"


def mark_task_delayed(task) -> None:
    task.delay_status = DELAYED_STATUS


def reset_task_delay(task) -> None:
    task.delay_status = NOT_DELAYED_STATUS

from collections.abc import Callable
from typing import TypeVar


ResultT = TypeVar("ResultT")


def execute_transaction(db, operation: Callable[[], ResultT]) -> ResultT:
    try:
        result = operation()
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise

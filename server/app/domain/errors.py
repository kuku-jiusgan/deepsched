class DomainError(Exception):
    """Base class for business errors mapped at the API boundary."""


class DomainNotFoundError(DomainError):
    pass


class DomainValidationError(DomainError):
    pass


class DomainConflictError(DomainError):
    pass

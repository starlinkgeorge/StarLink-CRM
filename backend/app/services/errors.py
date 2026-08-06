class NotFoundError(Exception):
    """Raised when a requested database record does not exist."""


class ConflictError(Exception):
    """Raised when a requested change violates a business uniqueness rule."""

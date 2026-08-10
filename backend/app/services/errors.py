class NotFoundError(Exception):
    """Raised when a requested database record does not exist."""


class ConflictError(Exception):
    """Raised when a requested change violates a business uniqueness rule."""


class ForbiddenError(Exception):
    """Raised when an authenticated user lacks access to a resource."""


class StorageConfigurationError(Exception):
    """Raised when the configured object-storage provider cannot be used."""

"""Custom exception hierarchy for AgentLens API."""

from __future__ import annotations


class AgentLensError(Exception):
    """Base exception for all AgentLens errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "An unexpected error occurred") -> None:
        super().__init__(message)
        self.message = message


class AuthenticationError(AgentLensError):
    status_code = 401
    error_code = "AUTHENTICATION_ERROR"

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(message)


class AuthorizationError(AgentLensError):
    status_code = 403
    error_code = "AUTHORIZATION_ERROR"

    def __init__(self, message: str = "Access denied") -> None:
        super().__init__(message)


class NotFoundError(AgentLensError):
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message)


class ValidationError(AgentLensError):
    status_code = 422
    error_code = "VALIDATION_ERROR"

    def __init__(self, message: str = "Validation failed") -> None:
        super().__init__(message)


class RateLimitError(AgentLensError):
    status_code = 429
    error_code = "RATE_LIMIT_EXCEEDED"

    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class ServiceUnavailableError(AgentLensError):
    status_code = 503
    error_code = "SERVICE_UNAVAILABLE"

    def __init__(self, message: str = "Service temporarily unavailable") -> None:
        super().__init__(message)

from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status


class BaseAppException(HTTPException):
    """
    Base application exception class. All custom application exceptions should inherit from this class.
    """
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Unknown error occurred."
    headers: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        detail: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Args:
            detail: Description about the error
            headers: HTTP response headers
            **kwargs: Additional context information (can be added to the error message)
        """
        self.extra_info = kwargs

        # If detail is provided, use it instead of the class default value
        actual_detail = detail if detail is not None else self.detail

        # If there is additional info and detail is a string, enrich the detail
        if self.extra_info and isinstance(actual_detail, str):
            actual_detail = (f"{actual_detail} Extra info: {self.extra_info}")

        # If headers are provided, use them instead of the class default value
        actual_headers = headers if headers is not None else self.headers

        # Call the parent class's __init__ method
        super().__init__(
            status_code=self.status_code,
            detail=actual_detail,
            headers=actual_headers
        )


class NotAuthenticatedException(BaseAppException):
    """User authentication error"""
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Unauthenticated user"
    headers = {"WWW-Authenticate": "Bearer"}


class PermissionDeniedException(BaseAppException):
    """Permission error"""
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Permission denied"


class NotFoundException(BaseAppException):
    """Resource not found error"""
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class AlreadyExistsException(BaseAppException):
    """Resource already exists error"""
    status_code = status.HTTP_409_CONFLICT
    detail ="Resource already exists"


class ValidationException(BaseAppException):
    """Data validation error"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation error"

    def __init__(
        self,
        detail: Optional[str] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ):
        """
        Args:
            detail: General description about the error
            errors: List of validation errors
            **kwargs: Additional context information
        """
        if errors:
            # If there is an errors list, create detail dynamically
            super().__init__(detail=detail, validation_errors=errors, **kwargs)
        else:
            super().__init__(detail=detail, **kwargs)


class DatabaseException(BaseAppException):
    """Database error"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Error occurred while accessing the database."


class ExternalServiceException(BaseAppException):
    """External service error"""
    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "External service error occurred."


class RateLimitException(BaseAppException):
    """Request limit exceeded error"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Rate limit exceeded. Please try again later."

    def __init__(
        self,
        detail: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Args:
            detail: Description about the error
            retry_after: How many seconds to wait before retrying
            **kwargs: Additional context information
        """
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(detail=detail, headers=headers, **kwargs)


class ServiceUnavailableException(BaseAppException):
    """Service unavailable error"""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Service unavailable. Please try again later."

    def __init__(
        self,
        detail: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Args:
            detail: Description about the error
            retry_after: How many seconds to wait before retrying
            **kwargs: Additional context information
        """
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(detail=detail, headers=headers, **kwargs)

# Login credentials exception
class InvalidCredentialsException(BaseAppException):
    """Invalid credentials error"""
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Invalid credentials provided."


class UnauthorizedException(BaseAppException):
    """Unauthorized access error"""
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Unauthorized access"
    headers = {"WWW-Authenticate": "Bearer"}


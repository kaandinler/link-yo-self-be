import logging
import traceback
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from core.exceptions import BaseAppException, DatabaseException
from core.schemas.response import ErrorResponse

logger = logging.getLogger(__name__)


async def catch_exceptions_middleware(request: Request, call_next: Callable):
    """
    Global exception catching middleware.
    Catches application-wide exceptions and converts them to appropriate HTTP responses.
    """
    try:
        return await call_next(request)
    except BaseAppException as exc:
        # If it's an exception we've defined, use it directly
        logger.warning(
            f"Handled error: {exc.__class__.__name__}. Details: {exc.detail}"
        )
        error_response = ErrorResponse.create(message=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.dict(),
            headers=exc.headers,
        )
    except SQLAlchemyError as exc:
        # Special handling for database errors
        logger.error(f"Database error: {str(exc)}")
        logger.debug(traceback.format_exc())
        db_exception = DatabaseException(detail=f"Database error: {str(exc)}")
        error_response = ErrorResponse.create(message="A database error occurred. Please try again later.")
        return JSONResponse(
            status_code=db_exception.status_code,
            content=error_response.dict(),
        )
    except Exception as exc:
        # For undefined error situations
        error_detail = f"Unexpected error: {str(exc)}"
        logger.error(error_detail)
        logger.debug(traceback.format_exc())

        error_response = ErrorResponse.create(message=error_detail)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.dict(),
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Adds exception handlers to the FastAPI application.
    """
    app.middleware("http")(catch_exceptions_middleware)

    # Special handlers for specific status codes
    @app.exception_handler(status.HTTP_404_NOT_FOUND)
    async def not_found_handler(request: Request, exc) -> JSONResponse:
        error_response = ErrorResponse.create(
            message=f"Requested resource not found: {request.url.path}"
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content=error_response.dict()
        )

    @app.exception_handler(status.HTTP_405_METHOD_NOT_ALLOWED)
    async def method_not_allowed_handler(request: Request, exc) -> JSONResponse:
        error_response = ErrorResponse.create(
            message=f"Method '{request.method}' not allowed for the requested resource: {request.url.path}"
        )
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content=error_response.dict()
        )

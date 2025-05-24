import logging
import traceback
from typing import Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from core.exceptions import BaseAppException, DatabaseException

logger = logging.getLogger(__name__)


async def catch_exceptions_middleware(request: Request, call_next: Callable):
    """
    Genel hata yakalama middleware'i.
    Uygulama genelindeki hataları yakalar ve uygun HTTP yanıtlarına dönüştürür.
    """
    try:
        return await call_next(request)
    except BaseAppException as exc:
        # Zaten bizim tanımladığımız bir istisna ise, direkt kullan
        logger.warning(
            f"İşlenen hata: {exc.__class__.__name__}. Detaylar: {exc.detail}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )
    except SQLAlchemyError as exc:
        # Veritabanı hataları için özel işleme
        logger.error(f"Veritabanı hatası: {str(exc)}")
        logger.debug(traceback.format_exc())
        db_exception = DatabaseException(detail=f"Veritabanı hatası: {str(exc)}")
        return JSONResponse(
            status_code=db_exception.status_code,
            content={"DB Error occured. Please try again later."},
        )
    except Exception as exc:
        # Tanımlanmamış bir hata durumunda
        error_detail = f"Unexpected error: {str(exc)}"
        logger.error(error_detail)
        logger.debug(traceback.format_exc())

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": error_detail},
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Exception handler'ları FastAPI uygulamasına ekler.
    """
    app.middleware("http")(catch_exceptions_middleware)

    # Belirli durum kodları için özel işleyiciler
    @app.exception_handler(status.HTTP_404_NOT_FOUND)
    async def not_found_handler(request: Request, exc) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Requested resource not found: {request.url.path}"}
        )

    @app.exception_handler(status.HTTP_405_METHOD_NOT_ALLOWED)
    async def method_not_allowed_handler(request: Request, exc) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content={
                "detail": f"Method '{request.method}' not allowed for the requested resource: {request.url.path}"
            }
        )

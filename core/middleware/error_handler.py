import logging
import traceback
from collections.abc import Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from core.exceptions import BaseAppException, DatabaseException
from core.schemas.response import ErrorResponse

logger = logging.getLogger(__name__)


async def catch_exceptions_middleware(request: Request, call_next: Callable):
    """Hicbir istegin sarmalanmamis bir istisnayla bitmemesini saglar.

    STARLETTE YIGININDAKI YERI (olculdu): ServerErrorMiddleware -> kullanici
    middleware'leri (burasi) -> ExceptionMiddleware -> router. Yani
    `app.exception_handler(...)` ile KAYITLI bir sinif buraya ULASMADAN,
    daha icerideki ExceptionMiddleware tarafindan karsilaniyor. Asagidaki
    `except BaseAppException` dali bu yuzden normal HTTP akisinda
    calismiyor; olcum icin kucuk bir uygulamada PermissionDeniedException
    firlatildi ve yanit setup_exception_handlers'in kaydettigi
    handler'dan dondu, bu daldan degil.

    Dal yine de DURUYOR: tek islevi, o handler bir gun kaldirilirsa
    uygulama hatalarinin 500'e dusmemesi. Kapsamda gorunmez bir yedek
    olmamasi icin dogrudan cagrilarak test ediliyor
    (bkz. tests/test_error_handler.py).

    Gercekte buraya ulasan sey, ExceptionMiddleware'in tanimadigi
    istisnalar: SQLAlchemyError ve beklenmeyen her sey.
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
            content=error_response.model_dump(),
            headers=exc.headers,
        )
    except SQLAlchemyError as exc:
        # Special handling for database errors
        logger.error(f"Database error: {exc!s}")
        logger.debug(traceback.format_exc())
        db_exception = DatabaseException(detail=f"Database error: {exc!s}")
        error_response = ErrorResponse.create(
            message="A database error occurred. Please try again later."
        )
        return JSONResponse(
            status_code=db_exception.status_code,
            content=error_response.model_dump(),
        )
    except Exception as exc:  # noqa: BLE001 - global catch-all middleware, bilincli
        # BEKLENMEYEN HATANIN METNI ISTEMCIYE GITMIYOR.
        #
        # Onceki hali `ErrorResponse.create(message=f"Unexpected error: {exc!s}")`
        # idi, yani yakalanan istisnanin metni oldugu gibi HTTP govdesine
        # yaziliyordu. Olculdu -- kucuk bir uygulamaya bilerek sizdirici bir
        # hata koyup istek atildi:
        #
        #     GET /beklenmeyen -> 500
        #     {"status":"error",
        #      "message":"Unexpected error: GIZLI_ANAHTAR_abc123
        #                  /home/user/uygulama/ayarlar.py", ...}
        #
        # Beklenmeyen hatalar tam da metni kontrol edilmeyen hatalardir:
        # icinde SQL parcasi, dosya yolu, ortam degiskeni ya da baska bir
        # kullanicinin verisi olabilir. Hemen yukaridaki SQLAlchemyError
        # dali bunu zaten dogru yapiyordu (genel mesaj donup ayrintiyi
        # loga yaziyor); bu dal ayni kurala getirildi.
        #
        # Ayrinti KAYBOLMUYOR: log'a tam metin ve traceback yaziliyor.
        logger.error(f"Unexpected error: {exc!s}")
        logger.debug(traceback.format_exc())

        error_response = ErrorResponse.create(
            message="An unexpected error occurred. Please try again later."
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=error_response.model_dump(),
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """
    Adds exception handlers to the FastAPI application.
    """
    app.middleware("http")(catch_exceptions_middleware)

    # BaseAppException HTTPException'dan turedigi icin Starlette'in
    # ExceptionMiddleware'i onu disaridaki catch_exceptions_middleware'e
    # ulasmadan yakalayip ham {"detail": ...} olarak donduruyordu. Bu handler
    # tum uygulama hatalarinin ayni ErrorResponse zarfini kullanmasini saglar.
    # (main.py'deki daha spesifik handler'lar tam sinif eslesmesiyle oncelikli.)
    @app.exception_handler(BaseAppException)
    async def app_exception_handler(
        request: Request, exc: BaseAppException
    ) -> JSONResponse:
        logger.warning(
            f"Handled error: {exc.__class__.__name__}. Details: {exc.detail}"
        )
        error_response = ErrorResponse.create(message=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=exc.headers,
        )

    # Special handlers for specific status codes
    @app.exception_handler(status.HTTP_404_NOT_FOUND)
    async def not_found_handler(request: Request, exc) -> JSONResponse:
        error_response = ErrorResponse.create(
            message=f"Requested resource not found: {request.url.path}"
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND, content=error_response.model_dump()
        )

    @app.exception_handler(status.HTTP_405_METHOD_NOT_ALLOWED)
    async def method_not_allowed_handler(request: Request, exc) -> JSONResponse:
        error_response = ErrorResponse.create(
            message=f"Method '{request.method}' not allowed for the requested resource: {request.url.path}"
        )
        return JSONResponse(
            status_code=status.HTTP_405_METHOD_NOT_ALLOWED,
            content=error_response.model_dump(),
        )

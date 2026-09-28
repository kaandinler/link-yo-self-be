import logging
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

# Import the db module for session factory setup
import db
from core.exceptions import (
    DatabaseException,
    InvalidCredentialsException,
    NotAuthenticatedException,
    NotFoundException,
    PermissionDeniedException,
)
from core.middleware.error_handler import setup_exception_handlers
from core.schemas.response import ErrorResponse
from di.container import Container
from routers import (
    analytics_router,
    auth_router,
    link_router,
    platform_router,
    profile_router,
    public_router,
    social_account_router,
    user_router,
)
from settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Uygulama yasam dongusu.

    @app.on_event("startup"/"shutdown") FastAPI'de deprecated; lifespan
    context manager'i hem baslangici hem kapanisi tek yerde tutuyor.
    """
    logger.info("Starting LinkYoSelf API")
    yield
    logger.info("Shutting down LinkYoSelf API")


def cors_kaynaklari() -> list[str]:
    """Tarayicidan gelen isteklerde kabul edilecek origin listesi.

    NEDEN FAIL-CLOSED: onceki hali `settings.allowed_origins or ["*"]`
    idi ve hemen altinda allow_credentials=True duruyordu. Starlette bu
    ikisini birlikte gorunce yanita `*` YAZMIYOR, ISTEGIN ORIGIN'INI
    YANSITIYOR. Calisan sunucuda olculdu:

        $ curl -i -X OPTIONS .../api/v1/profile/me \
            -H "Origin: https://kotu-site.example" ...
        access-control-allow-origin: https://kotu-site.example
        access-control-allow-credentials: true

    Yani ALLOWED_ORIGINS yazmayi unutan bir uretim dagitimi, hicbir
    uyari vermeden "her siteye acik" hale geliyordu. Bugun bunun tek
    basina veri sizdirmadigi dogru -- token Authorization basligiyla
    gidiyor, tarayici onu kendiliginden eklemiyor. Ama bu, ayarin dogru
    oldugu anlamina gelmiyor: cerez tabanli bir oturuma gecildigi gun
    ayni satir sessizce bir acik haline gelir.

    Sessizce acik olmaktansa acikca baslamamak daha iyi: uretimde liste
    bossa uygulama ayaga kalkmiyor ve hata neyin eksik oldugunu
    soyluyor. Gelistirmede `*` yerine frontend adresi kullaniliyor --
    iki ortam ayni sekle sahip olsun ki uretimde surpriz cikmasin.
    """
    if settings.allowed_origins:
        return settings.allowed_origins

    if settings.environment == "production":
        raise RuntimeError(
            "ALLOWED_ORIGINS bos. Uretimde CORS listesi acikca "
            "verilmeli: bos birakilinca her origin kabul edilirdi."
        )

    return [settings.frontend_url]


def guvenilir_adresler() -> list[str]:
    """TrustedHostMiddleware'in kabul ettigi Host basliklari.

    Ayni hata sekli: `allowed_hosts=None` verildiginde Starlette listeyi
    ["*"] yapiyor, yani uretim icin acilan kontrol hicbir sey
    yapmiyordu. Burasi yalnizca uretimde cagriliyor, o yuzden dogrudan
    hata veriyor.
    """
    if settings.allowed_hosts:
        return settings.allowed_hosts

    raise RuntimeError(
        "ALLOWED_HOSTS bos. Uretimde Host kontrolu acikca verilmeli: "
        "bos birakilinca her Host basligi kabul edilirdi."
    )


def create_app() -> FastAPI:
    # Create FastAPI instance
    app = FastAPI(
        title="LinkYoSelf API",
        description="API for managing social media links",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Configure security for production
    if settings.environment == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=guvenilir_adresler())
        app.add_middleware(HTTPSRedirectMiddleware)

    # Configure CORS
    #
    # allow_origins asla ["*"] olmuyor (bkz. cors_kaynaklari): `*` ile
    # allow_credentials=True bir arada anlamli degil -- Starlette o
    # durumda origin'i yansitiyor ve liste bir sey kisitlamiyor.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_kaynaklari(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Set up exception handlers
    setup_exception_handlers(app)

    # Add specific exception handlers
    @app.exception_handler(NotAuthenticatedException)
    async def unauthorized_exception_handler(
        request: Request, exc: NotAuthenticatedException
    ):
        error_response = ErrorResponse.create(message="Unauthorized access")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=exc.headers,
        )

    @app.exception_handler(PermissionDeniedException)
    async def permission_denied_exception_handler(
        request: Request, exc: PermissionDeniedException
    ):
        error_response = ErrorResponse.create(message=exc.detail)
        return JSONResponse(
            status_code=exc.status_code, content=error_response.model_dump()
        )

    @app.exception_handler(NotFoundException)
    async def not_found_exception_handler(request: Request, exc: NotFoundException):
        error_response = ErrorResponse.create(message="Resource not found")
        return JSONResponse(
            status_code=exc.status_code, content=error_response.model_dump()
        )

    @app.exception_handler(DatabaseException)
    async def database_exception_handler(request: Request, exc: DatabaseException):
        logger.error(f"Database Error: {exc.detail}")
        error_response = ErrorResponse.create(
            message="A database error occurred. Please try again later."
        )
        return JSONResponse(
            status_code=exc.status_code, content=error_response.model_dump()
        )

    @app.exception_handler(InvalidCredentialsException)
    async def invalid_credentials_exception_handler(
        request: Request, exc: InvalidCredentialsException
    ):
        error_response = ErrorResponse.create(message="Invalid credentials")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=exc.headers,
        )

    # Create and configure the DI container
    container = Container()

    # Store container reference in app state
    app.container = container

    # Initialize database session factory
    db.set_session_factory(container.async_session_factory())

    # Wire container to modules that need dependency injection
    container.wire(
        modules=[
            "routers.user_router",
            "routers.auth_router",
            "routers.link_router",  # EKLENDI
            "routers.profile_router",  # EKLENDI
            "routers.v1.user_router",
            "routers.v1.auth_router",
            "routers.v1.link_router",  # EKLENDI
            "routers.v1.profile_router",  # EKLENDI
            "routers.public_router",
            "routers.v1.public_router",
            "routers.analytics_router",
            "routers.v1.analytics_router",
            "routers.social_account_router",
            "routers.v1.social_account_router",
            "routers.platform_router",
            "routers.v1.platform_router",
            "deps",
        ]
    )

    # V1 API router'i olustur
    api_v1_router = APIRouter(prefix="/api/v1")

    # Router'lari API v1 router'a ekle.
    #
    # ONCEDEN her biri add_response_model(...) ile "sarmalaniyordu".
    # O sarmalayici HICBIR SEY YAPMIYORDU ve kaldirildi: router
    # metotlarini (router.get/post/...) degistiriyordu, ama rotalar
    # modul import edilirken @router.get(...) dekoratoruyle ZATEN
    # kaydedilmis oluyordu -- yani degistirilen metotlar hic cagrilmadi.
    #
    # Olculdu: 58 rotanin hicbirinde sarmalayicinin govdesi calismadi
    # (wrap_response cagrilma sayisi: 0) ve sarmalayici tamamen devre
    # disi birakildiginda uretilen OpenAPI semasi 41 yol icin BIREBIR
    # ayni cikti.
    #
    # Yanitlarin SuccessResponse zarfina girmesini saglayan sey bu degil;
    # her uc bunu kendi imzasinda acikca yaziyor
    # (response_model=SuccessResponse[...]) ve govdede
    # SuccessResponse.create(...) donduruyor.
    api_v1_router.include_router(user_router.router)
    api_v1_router.include_router(auth_router.router)
    api_v1_router.include_router(link_router.router)
    api_v1_router.include_router(profile_router.router)
    api_v1_router.include_router(public_router.router)
    api_v1_router.include_router(analytics_router.router)
    api_v1_router.include_router(social_account_router.router)
    api_v1_router.include_router(platform_router.router)

    # API v1 router'ı uygulamaya ekle
    app.include_router(api_v1_router)

    return app


# Create the app instance
app = create_app()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "online", "message": "LinkYoSelf API is running"}

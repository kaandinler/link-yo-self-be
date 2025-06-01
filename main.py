import logging
from fastapi import FastAPI, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse

# Import the db module for session factory setup
import db
from di.container import Container
from settings import settings
from routers import user_router, auth_router, link_router, profile_router
from core.exceptions import (
    NotAuthenticatedException,
    PermissionDeniedException,
    NotFoundException,
    DatabaseException, InvalidCredentialsException
)
from core.middleware.error_handler import setup_exception_handlers
from core.utils.response_wrapper import add_response_model
from core.schemas.response import ErrorResponse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    # Create FastAPI instance
    app = FastAPI(
        title="LinkYoSelf API",
        description="API for managing social media links",
        version="0.1.0"
    )

    # Configure security for production
    if settings.environment == "production":
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
        app.add_middleware(HTTPSRedirectMiddleware)

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Set up exception handlers
    setup_exception_handlers(app)

    # Add specific exception handlers
    @app.exception_handler(NotAuthenticatedException)
    async def unauthorized_exception_handler(request: Request, exc: NotAuthenticatedException):
        error_response = ErrorResponse.create(message="Unauthorized access")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=exc.headers
        )

    @app.exception_handler(PermissionDeniedException)
    async def permission_denied_exception_handler(request: Request, exc: PermissionDeniedException):
        error_response = ErrorResponse.create(message=exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump()
        )

    @app.exception_handler(NotFoundException)
    async def not_found_exception_handler(request: Request, exc: NotFoundException):
        error_response = ErrorResponse.create(message="Resource not found")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump()
        )

    @app.exception_handler(DatabaseException)
    async def database_exception_handler(request: Request, exc: DatabaseException):
        logger.error(f"Database Error: {exc.detail}")
        error_response = ErrorResponse.create(message="A database error occurred. Please try again later.")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump()
        )

    @app.exception_handler(InvalidCredentialsException)
    async def invalid_credentials_exception_handler(request: Request, exc: InvalidCredentialsException):
        error_response = ErrorResponse.create(message="Invalid credentials")
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump(),
            headers=exc.headers
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
            "deps"
        ]
    )

    # Router'ları BaseResponseModel ile sarmalama
    wrapped_user_router = add_response_model(user_router.router)
    wrapped_auth_router = add_response_model(auth_router.router)
    wrapped_link_router = add_response_model(link_router.router)
    wrapped_profile_router = add_response_model(profile_router.router)

    # V1 API router'ı oluştur
    api_v1_router = APIRouter(prefix="/api/v1")

    # Router'ları API v1 router'a ekle
    api_v1_router.include_router(wrapped_user_router)
    api_v1_router.include_router(wrapped_auth_router)
    api_v1_router.include_router(wrapped_link_router)
    api_v1_router.include_router(wrapped_profile_router)

    # API v1 router'ı uygulamaya ekle
    app.include_router(api_v1_router)

    return app


# Create the app instance
app = create_app()


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "online", "message": "LinkYoSelf API is running"}


@app.on_event("startup")
async def startup_event():
    logger.info("Starting LinkYoSelf API")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down LinkYoSelf API")


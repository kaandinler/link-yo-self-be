import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
from fastapi.responses import JSONResponse

# Import the db module for session factory setup
import db
from di.container import Container
from settings import settings
from routers import user_router, auth_router  # Import link_router when ready
from core.exceptions import (
    NotAuthenticatedException,
    PermissionDeniedException,
    NotFoundException,
    DatabaseException
)
from core.middleware.error_handler import setup_exception_handlers
from core.utils.response_wrapper import add_response_model

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
        return JSONResponse(
            status_code=exc.status_code,
            content={"Unauthorized"},
            headers=exc.headers
        )

    @app.exception_handler(PermissionDeniedException)
    async def permission_denied_exception_handler(request: Request, exc: PermissionDeniedException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )

    @app.exception_handler(NotFoundException)
    async def not_found_exception_handler(request: Request, exc: NotFoundException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"Not Found"},
        )

    @app.exception_handler(DatabaseException)
    async def database_exception_handler(request: Request, exc: DatabaseException):
        logger.error(f"Database Error: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": "Database error occurred. Please try again later."},
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
            # "routers.link_router",  # Uncomment when ready
            "deps"
        ]
    )

    # Router'ları BaseResponseModel ile sarmalama
    wrapped_user_router = add_response_model(user_router.router)
    wrapped_auth_router = add_response_model(auth_router.router)
    # wrapped_link_router = add_response_model(link_router.router)  # Uncomment when ready

    # Register wrapped routers
    app.include_router(wrapped_user_router)
    app.include_router(wrapped_auth_router)
    # app.include_router(wrapped_link_router)  # Uncomment when ready

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


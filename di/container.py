from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.auth.auth_service import AuthService
from core.email.sender import build_email_sender
from repositories.analytics.analytics_event_repository import (
    AnalyticsEventRepository,
)
from repositories.auth.email_verification_repository import (
    EmailVerificationRepository,
)
from repositories.auth.password_reset_repository import PasswordResetRepository
from repositories.auth.refresh_token_repository import RefreshTokenRepository
from repositories.link.link_repository import LinkRepository  # EKLENDI
from repositories.user.user_repository import UserRepository
from services.analytics.analytics_service import AnalyticsService
from services.link.link_service import LinkService  # EKLENDI
from services.user.user_service import UserService
from settings import settings


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        packages=["routers", "core.auth"]
    )

    # Configuration
    config = providers.Configuration()

    # Database settings
    config.database_url.from_value(settings.database_url)

    # Sifre sifirlama / e-posta ayarlari
    config.frontend_url.from_value(settings.frontend_url)
    config.password_reset_expire_minutes.from_value(
        settings.password_reset_token_expire_minutes
    )
    config.email_verification_expire_minutes.from_value(
        settings.email_verification_token_expire_minutes
    )

    # Engine log ayari
    config.db_echo.from_value(settings.db_echo)

    # JWT settings
    config.jwt_secret_key.from_value(settings.secret_key)
    config.jwt_algorithm.from_value(settings.algorithm)
    config.jwt_expire_minutes.from_value(settings.access_token_expire_minutes)

    # Database
    engine = providers.Singleton(
        create_async_engine,
        config.database_url,
        echo=config.db_echo,
        future=True
    )

    async_session_factory = providers.Singleton(
        async_sessionmaker,
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False
    )

    # Repositories
    user_repository = providers.Factory(
        UserRepository,
        session_factory=async_session_factory
    )

    refresh_token_repository = providers.Factory(
        RefreshTokenRepository,
        session_factory=async_session_factory
    )

    password_reset_repository = providers.Factory(
        PasswordResetRepository,
        session_factory=async_session_factory
    )

    email_verification_repository = providers.Factory(
        EmailVerificationRepository,
        session_factory=async_session_factory
    )

    email_sender = providers.Singleton(build_email_sender)

    # Link repository EKLENDI
    link_repository = providers.Factory(
        LinkRepository,
        session_factory=async_session_factory
    )

    analytics_event_repository = providers.Factory(
        AnalyticsEventRepository,
        session_factory=async_session_factory
    )

    # Services
    user_service = providers.Factory(
        UserService,
        user_repo=user_repository,
        refresh_token_repo=refresh_token_repository,
        event_repo=analytics_event_repository,
    )

    auth_service = providers.Factory(
        AuthService,
        user_service=user_service,
        user_repository=user_repository,
        refresh_token_repository=refresh_token_repository,
        password_reset_repository=password_reset_repository,
        email_verification_repository=email_verification_repository,
        email_sender=email_sender,
        secret_key=config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
        expire_minutes=config.jwt_expire_minutes,
        frontend_url=config.frontend_url,
        reset_expire_minutes=config.password_reset_expire_minutes,
        verification_expire_minutes=config.email_verification_expire_minutes,
    )

    # Link service EKLENDI
    link_service = providers.Factory(
        LinkService,
        link_repo=link_repository,
        event_repo=analytics_event_repository,
    )

    analytics_service = providers.Factory(
        AnalyticsService,
        link_repo=link_repository,
        event_repo=analytics_event_repository,
    )
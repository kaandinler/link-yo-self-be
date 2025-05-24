from dependency_injector import containers, providers
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from core.auth.auth_service import AuthService
from repositories.user.user_repository import UserRepository
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

    # JWT settings
    config.jwt_secret_key.from_value(settings.secret_key)
    config.jwt_algorithm.from_value(settings.algorithm)
    config.jwt_expire_minutes.from_value(settings.access_token_expire_minutes)

    # Database
    engine = providers.Singleton(
        create_async_engine,
        config.database_url,
        echo=True,
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

    # Services
    user_service = providers.Factory(
        UserService,
        user_repo=user_repository
    )

    auth_service = providers.Factory(
        AuthService,
        user_service=user_service,
        user_repository=user_repository,
        secret_key=config.jwt_secret_key,
        algorithm=config.jwt_algorithm,
        expire_minutes=config.jwt_expire_minutes,
    )
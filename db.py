from typing import AsyncGenerator, Callable, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

T = TypeVar('T')

# Will hold the reference to the container's session factory
_session_factory = None

def set_session_factory(factory):
    """Set the session factory to be used globally"""
    global _session_factory
    _session_factory = factory

def get_session_factory() -> async_sessionmaker:
    """Get the current session factory"""
    if _session_factory is None:
        raise RuntimeError("Session factory not initialized")
    return _session_factory

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provides a database session as an async generator with automatic transaction management.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def run_in_transaction(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Executes the given function within a transaction.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            result = await func(session, *args, **kwargs)
            await session.commit()
            return result
        except Exception:
            await session.rollback()
            raise

async def execute_without_transaction(func: Callable[..., T], *args, **kwargs) -> T:
    """
    Executes the given function with a session but without automatic transaction management.
    """
    factory = get_session_factory()
    async with factory() as session:
        session.expire_on_commit = False
        return await func(session, *args, **kwargs)
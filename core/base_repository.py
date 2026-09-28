from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import execute_without_transaction, run_in_transaction

T = TypeVar("T")


class BaseRepository(Generic[T]):
    def __init__(self, session_factory: Callable[[], AsyncSession]):
        self._session_factory = session_factory
        self._model_type: type[T] = None  # Will be set by child classes

    # Transactional operations (with auto commit/rollback)
    async def create(self, entity: T) -> T:
        async def _create(session: AsyncSession, entity_: T) -> T:
            session.add(entity_)
            await session.flush()
            return entity_

        return await run_in_transaction(_create, entity)

    async def update(self, entity: T) -> T:
        async def _update(session: AsyncSession, entity_: T) -> T:
            session.add(entity_)
            await session.flush()
            # onupdate/server_default ile hesaplanan alanlar (orn. updated_at)
            # flush sonrasi "expired" durumda kalir. Session kapandiktan sonra
            # bunlara erisilmek istendiginde DetachedInstanceError firlar, bu da
            # response serilestirmesini 500'e dusurur. Bu yuzden session hala
            # acikken degerleri geri yukluyoruz.
            await session.refresh(entity_)
            return entity_

        return await run_in_transaction(_update, entity)

    async def delete(self, entity: T) -> None:
        async def _delete(session: AsyncSession, entity_: T) -> None:
            await session.delete(entity_)

        await run_in_transaction(_delete, entity)

    # Non-transactional read operations (no auto commit)

    async def list_all(self, transactional: bool = False) -> Sequence[T]:
        async def _list_all(session: AsyncSession) -> Sequence[T]:
            result = await session.execute(select(self._model_type))
            return result.scalars().all()

        if transactional:
            return await run_in_transaction(_list_all)
        else:
            return await execute_without_transaction(_list_all)

    async def get_by_id(self, id_: Any, transactional: bool = False) -> T | None:
        async def _get_by_id(session: AsyncSession, id_value: Any) -> T | None:
            return await session.get(self._model_type, id_value)

        if transactional:
            return await run_in_transaction(_get_by_id, id_)
        return await execute_without_transaction(_get_by_id, id_)

    # Helper methods for custom queries
    async def execute_query(
        self,
        query_func: Callable[[AsyncSession, ...], Awaitable[T]],  # Note the Awaitable
        *args,
        transactional: bool = False,
        **kwargs,
    ) -> T:
        """
        Execute a custom query function with optional transaction management.

        Args:
            query_func: Async function that takes a session as first parameter
            *args: Additional arguments to pass to the query function
            transactional: Whether to run in a transaction (with commit/rollback)
            **kwargs: Additional keyword arguments to pass to the query function

        Returns:
            The result of the query function
        """
        if transactional:
            return await run_in_transaction(query_func, *args, **kwargs)
        return await execute_without_transaction(query_func, *args, **kwargs)


from typing import TypeVar, Generic, Optional, Sequence

from core.base_repository import BaseRepository

T = TypeVar('T')


class BaseService(Generic[T]):
    def __init__(self, repository: BaseRepository[T]):
        self.repository = repository

    async def create(self, entity: T) -> T:
        """Create a new entity"""
        return await self.repository.create(entity)

    async def get_by_id(self, entity_id: int) -> Optional[T]:
        """Get entity by ID"""
        return await self.repository.get_by_id(entity_id)

    async def list(self, model_class=None) -> Sequence[T]:
        """List all entities"""
        return await self.repository.list_all()

    async def update(self, entity: T) -> T:
        """Update entity"""
        return await self.repository.update(entity)

    async def delete(self, entity: T) -> None:
        """Delete entity"""
        await self.repository.delete(entity)
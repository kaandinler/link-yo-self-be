from typing import Optional, Sequence, Awaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import User


class UserRepository(BaseRepository[User]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = User

    async def list_users(self, transactional: bool = False) -> Awaitable[Sequence[User]]:
        """Get all users with optional transaction control"""
        return await self.list_all(transactional=transactional)

    async def get_user(self, user_id: int, transactional: bool = False) -> Optional[User]:
        """Get user by ID with optional transaction control"""
        return await self.get_by_id(user_id, transactional=transactional)

    async def get_by_username(self, username: str, transactional: bool = False) -> Optional[User]:
        """Get user by username with optional transaction control"""

        async def _get_by_username(session: AsyncSession, username_: str) -> Optional[User]:
            result = await session.execute(
                select(User).where(User.username == username_)
            )
            return result.scalars().first()

        # Use the execute_query helper for flexible transaction handling
        return await self.execute_query(_get_by_username, username, transactional=transactional)

    async def get_by_email(self, email: str, transactional: bool = False) -> Optional[User]:
        """Get user by email with optional transaction control"""

        async def _get_by_email(session: AsyncSession, email_: str) -> Optional[User]:
            result = await session.execute(
                select(User).where(User.email == email_)
            )
            return result.scalars().first()

        # Use the execute_query helper for flexible transaction handling
        return await self.execute_query(_get_by_email, email, transactional=transactional)

    async def create_user(self, user: User) -> User:
        """Create a new user (always transactional)"""
        return await self.create(user)

    async def update_user(self, user: User) -> User:
        """Update an existing user (always transactional)"""
        return await self.update(user)

    async def delete_user(self, user: User) -> None:
        """Delete a user (always transactional)"""
        await self.delete(user)

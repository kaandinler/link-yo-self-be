from typing import Optional, Sequence, Awaitable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
                # links eager yuklenmeli: User.profile_completion_percentage bu
                # iliskiye eriseyor ve session kapandiktan sonra lazy load
                # DetachedInstanceError firlatir.
                select(User)
                .options(selectinload(User.links))
                .where(User.username == username_)
            )
            return result.scalars().first()

        # Use the execute_query helper for flexible transaction handling
        return await self.execute_query(_get_by_username, username, transactional=transactional)

    async def get_by_email(self, email: str, transactional: bool = False) -> Optional[User]:
        """Get user by email with optional transaction control"""

        async def _get_by_email(session: AsyncSession, email_: str) -> Optional[User]:
            result = await session.execute(
                select(User)
                .options(selectinload(User.links))
                .where(User.email == email_)
            )
            return result.scalars().first()

        # Use the execute_query helper for flexible transaction handling
        return await self.execute_query(_get_by_email, email, transactional=transactional)

    async def get_public_profile(
        self, username: str, transactional: bool = False
    ) -> Optional[User]:
        """Public profil icin kullaniciyi linkleriyle birlikte getirir.

        Soft delete edilmis kullanicilar public sayfada gorunmez.
        """

        async def _get_public_profile(
            session: AsyncSession, username_: str
        ) -> Optional[User]:
            result = await session.execute(
                select(User)
                .options(selectinload(User.links))
                .where(User.username == username_, User.is_deleted.is_(False))
            )
            return result.scalars().first()

        return await self.execute_query(
            _get_public_profile, username, transactional=transactional
        )

    async def create_user(self, user: User) -> User:
        """Create a new user (always transactional)"""
        return await self.create(user)

    async def update_user(self, user: User) -> User:
        """Update an existing user (always transactional)"""
        return await self.update(user)

    async def delete_user(self, user: User) -> None:
        """Delete a user (always transactional)"""
        await self.delete(user)

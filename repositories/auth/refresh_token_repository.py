from typing import Optional, Sequence, Awaitable
from sqlalchemy import select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime

from core.base_repository import BaseRepository
from models import RefreshToken


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = RefreshToken

    async def create_token(self, refresh_token: RefreshToken) -> RefreshToken:
        """Yeni bir refresh token oluşturur"""
        return await self.create(refresh_token)

    async def get_by_token(self, token: str, transactional: bool = False) -> Optional[RefreshToken]:
        """Token değeri ile refresh token kaydını bulur"""

        async def _get_by_token(session: AsyncSession, token_value: str) -> Optional[RefreshToken]:
            result = await session.execute(
                select(RefreshToken).where(RefreshToken.token == token_value)
            )
            return result.scalars().first()

        return await self.execute_query(_get_by_token, token, transactional=transactional)

    async def get_valid_token(self, token: str, transactional: bool = False) -> Optional[RefreshToken]:
        """Geçerli bir refresh token kaydını bulur (süresi dolmamış ve revoke edilmemiş)"""

        async def _get_valid_token(session: AsyncSession, token_value: str) -> Optional[RefreshToken]:
            result = await session.execute(
                select(RefreshToken).where(
                    and_(
                        RefreshToken.token == token_value,
                        RefreshToken.is_revoked == False,
                        RefreshToken.expires_at > datetime.utcnow()
                    )
                )
            )
            return result.scalars().first()

        return await self.execute_query(_get_valid_token, token, transactional=transactional)

    async def revoke_token(self, token: str) -> None:
        """Refresh token'ı geçersiz kılar"""

        async def _revoke_token(session: AsyncSession, token_value: str) -> None:
            await session.execute(
                update(RefreshToken)
                .where(RefreshToken.token == token_value)
                .values(is_revoked=True)
            )
            await session.commit()

        return await self.execute_query(_revoke_token, token, transactional=True)

    async def revoke_all_user_tokens(self, user_id: int) -> None:
        """Kullanıcının tüm refresh token'larını geçersiz kılar"""

        async def _revoke_all_user_tokens(session: AsyncSession, user_id_: int) -> None:
            await session.execute(
                update(RefreshToken)
                .where(
                    and_(
                        RefreshToken.user_id == user_id_,
                        RefreshToken.is_revoked == False
                    )
                )
                .values(is_revoked=True)
            )
            await session.commit()

        return await self.execute_query(_revoke_all_user_tokens, user_id, transactional=True)


from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import RefreshToken
from utils.time_utils import utcnow


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = RefreshToken

    async def create_token(self, refresh_token: RefreshToken) -> RefreshToken:
        """Yeni bir refresh token oluşturur"""
        return await self.create(refresh_token)

    async def get_by_token(self, token: str, transactional: bool = False) -> RefreshToken | None:
        """Token değeri ile refresh token kaydını bulur"""

        async def _get_by_token(session: AsyncSession, token_value: str) -> RefreshToken | None:
            result = await session.execute(
                select(RefreshToken).where(RefreshToken.token == token_value)
            )
            return result.scalars().first()

        return await self.execute_query(_get_by_token, token, transactional=transactional)

    async def get_valid_token(self, token: str, transactional: bool = False) -> RefreshToken | None:
        """Geçerli bir refresh token kaydını bulur (süresi dolmamış ve revoke edilmemiş)"""

        async def _get_valid_token(session: AsyncSession, token_value: str) -> RefreshToken | None:
            result = await session.execute(
                select(RefreshToken).where(
                    and_(
                        RefreshToken.token == token_value,
                        # DIKKAT: Python'un `not` operatoru burada kullanilamaz;
                        # kolonu Python bool'una cevirip sorguyu WHERE false
                        # haline getirir. SQL karsiligi icin .is_(False) sart.
                        RefreshToken.is_revoked.is_(False),
                        RefreshToken.expires_at > utcnow()
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
                        RefreshToken.is_revoked.is_(False)
                    )
                )
                .values(is_revoked=True)
            )
            await session.commit()

        return await self.execute_query(_revoke_all_user_tokens, user_id, transactional=True)

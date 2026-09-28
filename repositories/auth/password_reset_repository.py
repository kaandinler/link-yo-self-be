from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import PasswordResetToken
from utils.time_utils import utcnow


class PasswordResetRepository(BaseRepository[PasswordResetToken]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = PasswordResetToken

    async def create_token(self, token: PasswordResetToken) -> PasswordResetToken:
        return await self.create(token)

    async def get_valid_by_hash(
        self, token_hash: str, transactional: bool = False
    ) -> PasswordResetToken | None:
        """Kullanilmamis ve suresi dolmamis token kaydini bulur."""

        async def _get(session: AsyncSession, value: str) -> PasswordResetToken | None:
            result = await session.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.token_hash == value,
                    PasswordResetToken.used_at.is_(None),
                    PasswordResetToken.expires_at > utcnow(),
                )
            )
            return result.scalars().first()

        return await self.execute_query(_get, token_hash, transactional=transactional)

    async def mark_used(self, token_hash: str) -> None:
        """Token'i kullanilmis olarak isaretler (tek kullanimlik)."""

        async def _mark(session: AsyncSession, value: str) -> None:
            await session.execute(
                update(PasswordResetToken)
                .where(PasswordResetToken.token_hash == value)
                .values(used_at=utcnow())
            )

        await self.execute_query(_mark, token_hash, transactional=True)

    async def invalidate_user_tokens(self, user_id: int) -> None:
        """Kullanicinin bekleyen tum sifirlama token'larini gecersiz kilar.

        Yeni bir talep geldiginde veya sifre degistiginde cagriliyor; boylece
        eski e-postalardaki baglantilar calismaz.
        """

        async def _invalidate(session: AsyncSession, uid: int) -> None:
            await session.execute(
                update(PasswordResetToken)
                .where(
                    PasswordResetToken.user_id == uid,
                    PasswordResetToken.used_at.is_(None),
                )
                .values(used_at=utcnow())
            )

        await self.execute_query(_invalidate, user_id, transactional=True)

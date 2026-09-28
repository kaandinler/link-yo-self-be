from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import EmailVerificationToken
from utils.time_utils import utcnow


class EmailVerificationRepository(BaseRepository[EmailVerificationToken]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = EmailVerificationToken

    async def create_token(
        self, token: EmailVerificationToken
    ) -> EmailVerificationToken:
        return await self.create(token)

    async def get_valid_by_hash(
        self, token_hash: str, transactional: bool = False
    ) -> EmailVerificationToken | None:
        """Kullanilmamis ve suresi dolmamis token kaydini bulur."""

        async def _get(
            session: AsyncSession, value: str
        ) -> EmailVerificationToken | None:
            result = await session.execute(
                select(EmailVerificationToken).where(
                    EmailVerificationToken.token_hash == value,
                    EmailVerificationToken.used_at.is_(None),
                    EmailVerificationToken.expires_at > utcnow(),
                )
            )
            return result.scalars().first()

        return await self.execute_query(_get, token_hash, transactional=transactional)

    async def mark_used(self, token_hash: str) -> None:
        """Token'i kullanilmis olarak isaretler (tek kullanimlik)."""

        async def _mark(session: AsyncSession, value: str) -> None:
            await session.execute(
                update(EmailVerificationToken)
                .where(EmailVerificationToken.token_hash == value)
                .values(used_at=utcnow())
            )

        await self.execute_query(_mark, token_hash, transactional=True)

    async def invalidate_user_tokens(self, user_id: int) -> None:
        """Kullanicinin bekleyen tum dogrulama token'larini gecersiz kilar.

        Yeni bir talep geldiginde cagriliyor: ayni anda birden fazla gecerli
        baglanti dolasmasin. Ozellikle adres degistirmede onemli -- eski bir
        e-postadaki baglanti, kullanicinin sonradan vazgectigi bir adrese
        gecis yapabilirdi.
        """

        async def _invalidate(session: AsyncSession, uid: int) -> None:
            await session.execute(
                update(EmailVerificationToken)
                .where(
                    EmailVerificationToken.user_id == uid,
                    EmailVerificationToken.used_at.is_(None),
                )
                .values(used_at=utcnow())
            )

        await self.execute_query(_invalidate, user_id, transactional=True)

    async def get_pending_email(
        self, user_id: int, transactional: bool = False
    ) -> str | None:
        """Kullanicinin onay bekleyen yeni adresi (varsa).

        Arayuz "x@y.com adresine baglanti gonderildi" diyebilsin diye.
        """

        async def _get(session: AsyncSession, uid: int) -> str | None:
            result = await session.execute(
                select(EmailVerificationToken.email)
                .where(
                    EmailVerificationToken.user_id == uid,
                    EmailVerificationToken.used_at.is_(None),
                    EmailVerificationToken.expires_at > utcnow(),
                )
                .order_by(EmailVerificationToken.id.desc())
                .limit(1)
            )
            return result.scalars().first()

        return await self.execute_query(_get, user_id, transactional=transactional)

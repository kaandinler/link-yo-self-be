# repositories/page_settings/page_settings_repository.py


from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import PageSettings


class PageSettingsRepository(BaseRepository[PageSettings]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = PageSettings

    async def get_by_user(self, user_id: int) -> PageSettings | None:
        """Kullanicinin ayar satiri; yoksa None.

        Tablo user_id uzerinde UNIQUE, yani en fazla bir satir var.
        Satirin YOKLUGU normal bir durum: hicbir ayara dokunmamis
        kullanicinin satiri hic olusmuyor -- kayit yalnizca ilk
        guncellemede yaziliyor. Okuma tarafinda varsayilanlar
        kullaniliyor (bkz. PageSettingsService.get_settings).
        """

        async def _get_by_user(
            session: AsyncSession, user_id_: int
        ) -> PageSettings | None:
            result = await session.execute(
                select(PageSettings).where(
                    and_(
                        PageSettings.user_id == user_id_,
                        PageSettings.is_deleted.is_(False),
                    )
                )
            )
            return result.scalars().first()

        return await self.execute_query(_get_by_user, user_id, transactional=False)

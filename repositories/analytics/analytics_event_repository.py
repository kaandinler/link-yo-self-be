# repositories/analytics/analytics_event_repository.py

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import EVENT_LINK_CLICK, AnalyticsEvent


class AnalyticsEventRepository(BaseRepository[AnalyticsEvent]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = AnalyticsEvent

    async def record(
        self, user_id: int, event_type: str, link_id: int | None = None
    ) -> None:
        """Tek bir olayi yazar.

        Olusan satir cagirana dondurulmuyor: olay kaydi bir yan etki,
        cagiranin (tiklama ucu, herkese acik profil) yanitini etkilemiyor.
        """

        async def _record(session: AsyncSession) -> None:
            session.add(
                AnalyticsEvent(
                    user_id=user_id,
                    event_type=event_type,
                    link_id=link_id,
                )
            )

        await self.execute_query(_record, transactional=True)

    async def daily_counts(
        self, user_id: int, since: datetime
    ) -> list[tuple[str, str, int]]:
        """Kullanicinin `since` tarihinden itibaren gunluk olay sayilari.

        (gun, olay_turu, adet) uclulerinden olusan bir liste doner. Gun,
        veritabaninin date() fonksiyonundan geldigi icin ISO metne
        normalize ediliyor: PostgreSQL date nesnesi, SQLite ise metin
        donduruyor (testler SQLite uzerinde kosuyor).

        Gunler UTC'ye gore ayriliyor.

        Gruplama veritabaninda yapiliyor: 90 gunluk bir araligin tum
        satirlarini Python'a cekmek gereksiz.
        """
        gun = func.date(AnalyticsEvent.created_at).label("gun")

        async def _counts(session: AsyncSession) -> list[tuple[str, str, int]]:
            result = await session.execute(
                select(gun, AnalyticsEvent.event_type, func.count())
                .where(AnalyticsEvent.user_id == user_id)
                .where(AnalyticsEvent.created_at >= since)
                .group_by(gun, AnalyticsEvent.event_type)
            )
            return [
                (_gune_metin(satir[0]), satir[1], satir[2])
                for satir in result.all()
            ]

        return await self.execute_query(_counts)

    async def daily_link_click_counts(
        self, user_id: int, since: datetime
    ) -> list[tuple[str, int, int]]:
        """Gunluk tiklama sayilari, link kirilimiyla.

        (gun, link_id, adet) uclulerinden olusan bir liste doner.

        link_id'si bos olan olaylar disarida kaliyor: silinmis bir linke ait
        tiklamalar (ON DELETE SET NULL) artik bir linke baglanamiyor. Genel
        zaman serisinde sayilmaya devam ediyorlar, yalnizca "hangi link"
        kirilimi onlar icin uretilemiyor.
        """
        gun = func.date(AnalyticsEvent.created_at).label("gun")

        async def _counts(session: AsyncSession) -> list[tuple[str, int, int]]:
            result = await session.execute(
                select(gun, AnalyticsEvent.link_id, func.count())
                .where(AnalyticsEvent.user_id == user_id)
                .where(AnalyticsEvent.event_type == EVENT_LINK_CLICK)
                .where(AnalyticsEvent.link_id.isnot(None))
                .where(AnalyticsEvent.created_at >= since)
                .group_by(gun, AnalyticsEvent.link_id)
            )
            return [
                (_gune_metin(satir[0]), satir[1], satir[2])
                for satir in result.all()
            ]

        return await self.execute_query(_counts)


def _gune_metin(deger: object) -> str:
    """date/datetime/metin -> 'YYYY-MM-DD'."""
    if isinstance(deger, str):
        # SQLite date() zaten bu bicimde doner; yine de saat kismi gelirse kes.
        return deger[:10]
    return deger.isoformat()[:10]

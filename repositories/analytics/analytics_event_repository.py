# repositories/analytics/analytics_event_repository.py

from datetime import datetime

from sqlalchemy import func, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import EVENT_LINK_CLICK, AnalyticsEvent


class AnalyticsEventRepository(BaseRepository[AnalyticsEvent]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = AnalyticsEvent

    async def record(
        self,
        user_id: int,
        event_type: str,
        link_id: int | None = None,
        referrer: str | None = None,
    ) -> None:
        """Tek bir olayi yazar.

        `referrer` normalize edilmis host olmali (bkz. utils.referrer);
        burada dogrulama yapilmiyor. None = dis bir kaynak yok.

        Olusan satir cagirana dondurulmuyor: olay kaydi bir yan etki,
        cagiranin (tiklama ucu, herkese acik profil) yanitini etkilemiyor.
        """

        async def _record(session: AsyncSession) -> None:
            session.add(
                AnalyticsEvent(
                    user_id=user_id,
                    event_type=event_type,
                    link_id=link_id,
                    referrer=referrer,
                )
            )

        await self.execute_query(_record, transactional=True)

    async def daily_counts(
        self, user_id: int, since: datetime, until: datetime | None = None
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
                .where(_ust_sinir(until))
                .group_by(gun, AnalyticsEvent.event_type)
            )
            return [
                (_gune_metin(satir[0]), satir[1], satir[2])
                for satir in result.all()
            ]

        return await self.execute_query(_counts)

    async def daily_link_click_counts(
        self, user_id: int, since: datetime, until: datetime | None = None
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
                .where(_ust_sinir(until))
                .group_by(gun, AnalyticsEvent.link_id)
            )
            return [
                (_gune_metin(satir[0]), satir[1], satir[2])
                for satir in result.all()
            ]

        return await self.execute_query(_counts)

    async def referrer_counts(
        self, user_id: int, since: datetime, until: datetime | None = None
    ) -> list[tuple[str | None, int]]:
        """Kullanicinin `since` tarihinden itibaren kaynak basina tiklamalari.

        (host, adet) ikililerinden olusan bir liste doner; host None ise
        dogrudan gelen tiklamalar.

        Yalnizca tiklamalar sayiliyor: profil goruntulenmesi sunucuda
        render edilirken kaydediliyor ve orada ziyaretcinin referrer'i
        elimizde olmuyor, dolayisiyla o satirlarin hepsi None olurdu ve
        "Direct"i yapay olarak sisirirdi.

        Gruplama veritabaninda: dagilimi cikarmak icin tum satirlari
        Python'a cekmeye gerek yok.
        """

        async def _counts(session: AsyncSession) -> list[tuple[str | None, int]]:
            result = await session.execute(
                select(AnalyticsEvent.referrer, func.count())
                .where(AnalyticsEvent.user_id == user_id)
                .where(AnalyticsEvent.event_type == EVENT_LINK_CLICK)
                .where(AnalyticsEvent.created_at >= since)
                .where(_ust_sinir(until))
                .group_by(AnalyticsEvent.referrer)
            )
            return [(satir[0], satir[1]) for satir in result.all()]

        return await self.execute_query(_counts)

    async def hourly_click_counts(
        self, user_id: int, since: datetime, until: datetime | None = None
    ) -> list[tuple[str, int, int]]:
        """Kullanicinin `since` tarihinden itibaren saat basina tiklamalari.

        (gun, saat, adet) uclulerinden olusan bir liste doner; gun ve saat
        UTC'ye gore. Saat dilimi cevrimi bilerek burada degil servis
        katmaninda: SQL'de IANA saat dilimi kullanmak PostgreSQL'e ozgu
        olurdu ve testler SQLite uzerinde kosuyor.

        Gruplama veritabaninda yapiliyor ve sonuc kucuk kaliyor: 90 gunluk
        aralikta en fazla 90 x 24 = 2160 satir. Ham olaylari Python'a
        cekmek, yogun bir hesapta on binlerce satir demekti.

        func.extract iki veritabaninda da calisiyor: SQLAlchemy bunu
        SQLite'ta STRFTIME'a ceviriyor.
        """
        gun = func.date(AnalyticsEvent.created_at).label("gun")
        saat = func.extract("hour", AnalyticsEvent.created_at).label("saat")

        async def _counts(session: AsyncSession) -> list[tuple[str, int, int]]:
            result = await session.execute(
                select(gun, saat, func.count())
                .where(AnalyticsEvent.user_id == user_id)
                .where(AnalyticsEvent.event_type == EVENT_LINK_CLICK)
                .where(AnalyticsEvent.created_at >= since)
                .where(_ust_sinir(until))
                .group_by(gun, saat)
            )
            return [
                (_gune_metin(satir[0]), int(satir[1]), satir[2])
                for satir in result.all()
            ]

        return await self.execute_query(_counts)



def _ust_sinir(until: datetime | None):
    """Araligin ust sinirini veren kosul; `until` yoksa her zaman dogru.

    NEDEN AYRI FONKSIYON: dort sorgu da ayni kosulu kuruyor ve `until`
    opsiyonel. Her birinde ayri bir if yazmak, birinde unutuldugunda
    yalnizca o ucun tarih araligini sessizce gormezden gelmesi demekti.

    Sinir disarida birakiliyor (`<`): cagiran taraf bitis gununun
    ertesinin baslangicini veriyor, boylece son gunun tamami kapsaniyor
    ve saniye/mikrosaniye yuvarlama sorusu hic dogmuyor.
    """
    if until is None:
        return true()
    return AnalyticsEvent.created_at < until


def _gune_metin(deger: object) -> str:
    """date/datetime/metin -> 'YYYY-MM-DD'."""
    if isinstance(deger, str):
        # SQLite date() zaten bu bicimde doner; yine de saat kismi gelirse kes.
        return deger[:10]
    return deger.isoformat()[:10]

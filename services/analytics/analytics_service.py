"""Pano ve analytics sayfasinin verisini hazirlar."""

from datetime import UTC, date, datetime, timedelta

from models import EVENT_LINK_CLICK, EVENT_PROFILE_VIEW, User
from repositories.analytics.analytics_event_repository import (
    AnalyticsEventRepository,
)
from repositories.link.link_repository import LinkRepository
from services.analytics.analytics_dto import (
    AnalyticsDayPoint,
    AnalyticsSummary,
    AnalyticsTimeseries,
    LinkClickStat,
    LinkDayPoint,
    LinkTimeseries,
    LinkTimeseriesResponse,
    ReferrerBreakdown,
    ReferrerKind,
    ReferrerSource,
)
from utils.time_utils import utcnow

# Ucun kabul ettigi araligin ust siniri. Uzun araliklar hem sorguyu hem de
# grafigi anlamsiz derecede yogunlastiriyor; gerekirse aylik bir uc eklenir.
MAX_DAYS = 90

# Kaynak listesinde ayri satir olarak gosterilecek en fazla host sayisi;
# kalanlar tek bir "diger" satirinda toplaniyor. Uzun kuyruk panoda okunur
# bir sey anlatmiyor, yalnizca listeyi uzatiyor.
MAX_SOURCES = 8


class AnalyticsService:
    def __init__(
        self,
        link_repo: LinkRepository,
        event_repo: AnalyticsEventRepository | None = None,
    ):
        self.link_repository = link_repo
        self.event_repository = event_repo

    async def get_summary(self, user: User) -> AnalyticsSummary:
        """Kullanicinin link ve profil istatistiklerini toplar.

        Pasif linkler de sayiliyor: kullanici bir linki gecici olarak
        kapattiginda o linkin gecmis tiklamalari toplamdan dusmemeli.
        """
        links = await self.link_repository.get_links_by_user(
            user.id, include_inactive=True
        )

        return AnalyticsSummary(
            username=user.username,
            profile_url_path=f"/{user.username}",
            total_links=len(links),
            active_links=sum(1 for link in links if link.is_active),
            total_clicks=sum(link.click_count for link in links),
            profile_view_count=user.profile_view_count or 0,
            links=[
                LinkClickStat.model_validate(link)
                for link in sorted(
                    links, key=lambda link: link.click_count, reverse=True
                )
            ],
        )

    @staticmethod
    def _aralik(days: int) -> tuple[int, date, date, datetime]:
        """Gun sayisindan araligi hesaplar: (gun_sayisi, ilk_gun, son_gun, baslangic).

        Gunler UTC'ye gore ayriliyor ve bugun araliga dahil.
        """
        days = max(1, min(days, MAX_DAYS))

        bugun = utcnow().date()
        baslangic_gun = bugun - timedelta(days=days - 1)
        # Gun basindan itibaren: sorgu gunun tamamini kapsamali.
        baslangic = datetime.combine(
            baslangic_gun, datetime.min.time(), tzinfo=UTC
        )

        return days, baslangic_gun, bugun, baslangic

    async def get_timeseries(self, user: User, days: int) -> AnalyticsTimeseries:
        """Son `days` gunun gunluk tiklama ve profil goruntulenme sayilari.

        Gunler UTC'ye gore ayriliyor ve bugun dahil. Olay olmayan gunler de
        sifir degerlerle donuyor.
        """
        days, baslangic_gun, bugun, baslangic = self._aralik(days)

        satirlar = (
            await self.event_repository.daily_counts(user.id, baslangic)
            if self.event_repository
            else []
        )

        tiklama: dict[str, int] = {}
        goruntulenme: dict[str, int] = {}
        for gun, olay_turu, adet in satirlar:
            if olay_turu == EVENT_LINK_CLICK:
                tiklama[gun] = tiklama.get(gun, 0) + adet
            elif olay_turu == EVENT_PROFILE_VIEW:
                goruntulenme[gun] = goruntulenme.get(gun, 0) + adet

        noktalar = []
        for gecen in range(days):
            gun = baslangic_gun + timedelta(days=gecen)
            anahtar = gun.isoformat()
            noktalar.append(
                AnalyticsDayPoint(
                    date=gun,
                    clicks=tiklama.get(anahtar, 0),
                    profile_views=goruntulenme.get(anahtar, 0),
                )
            )

        return AnalyticsTimeseries(
            days=days,
            start_date=baslangic_gun,
            end_date=bugun,
            total_clicks=sum(nokta.clicks for nokta in noktalar),
            total_profile_views=sum(nokta.profile_views for nokta in noktalar),
            points=noktalar,
        )

    async def get_link_timeseries(
        self, user: User, days: int
    ) -> LinkTimeseriesResponse:
        """Her linkin secili aralikteki gunluk tiklama egrisi.

        Aralikta hic tiklanmayan linkler de listede, sifir degerlerle.
        Siralama: aralik icindeki tiklamaya gore azalan, esitlikte linkin
        kendi sirasina (order_index) gore -- boylece hicbir tiklama
        yokken liste herkese acik sayfadaki sirayi izliyor.
        """
        days, baslangic_gun, bugun, baslangic = self._aralik(days)

        links = await self.link_repository.get_links_by_user(
            user.id, include_inactive=True
        )

        satirlar = (
            await self.event_repository.daily_link_click_counts(
                user.id, baslangic
            )
            if self.event_repository
            else []
        )

        # link_id -> gun -> adet
        sayaclar: dict[int, dict[str, int]] = {}
        for gun, link_id, adet in satirlar:
            sayaclar.setdefault(link_id, {})[gun] = (
                sayaclar.setdefault(link_id, {}).get(gun, 0) + adet
            )

        gunler = [
            baslangic_gun + timedelta(days=gecen) for gecen in range(days)
        ]

        seriler = []
        for link in links:
            link_sayaclari = sayaclar.get(link.id, {})
            noktalar = [
                LinkDayPoint(
                    date=gun, clicks=link_sayaclari.get(gun.isoformat(), 0)
                )
                for gun in gunler
            ]
            seriler.append(
                LinkTimeseries(
                    id=link.id,
                    title=link.title,
                    url=link.url,
                    is_active=link.is_active,
                    total_clicks=sum(nokta.clicks for nokta in noktalar),
                    points=noktalar,
                )
            )

        sira = {link.id: index for index, link in enumerate(links)}
        seriler.sort(key=lambda seri: (-seri.total_clicks, sira[seri.id]))

        return LinkTimeseriesResponse(
            days=days,
            start_date=baslangic_gun,
            end_date=bugun,
            links=seriler,
        )

    async def get_referrers(self, user: User, days: int) -> ReferrerBreakdown:
        """Secili aralikta tiklamalarin hangi siteden geldigi.

        Hicbir kaynagi olmayan bir aralik icin bos liste doner; cagiran taraf
        "henuz veri yok" durumunu sources'in bosluguyla ayirt edebiliyor.

        Dogrudan gelen tiklamalar ayri bir satir olarak listede: onlari
        gizlemek toplami tutarsiz gosterirdi ve "trafigimin ucte ikisini
        nereden geldigini bilmiyorum" da bir bilgi.
        """
        days, baslangic_gun, bugun, baslangic = self._aralik(days)

        satirlar = (
            await self.event_repository.referrer_counts(user.id, baslangic)
            if self.event_repository
            else []
        )

        dogrudan = sum(adet for host, adet in satirlar if not host)
        hostlar = sorted(
            ((host, adet) for host, adet in satirlar if host),
            key=lambda satir: (-satir[1], satir[0]),
        )

        kaynaklar = [
            ReferrerSource(kind=ReferrerKind.HOST, host=host, clicks=adet)
            for host, adet in hostlar[:MAX_SOURCES]
        ]

        if dogrudan:
            kaynaklar.append(
                ReferrerSource(kind=ReferrerKind.DIRECT, clicks=dogrudan)
            )

        # Dogrudan satiri da siralamaya giriyor: cogu sitede en buyuk pay
        # onda ve listenin ortasinda kaybolmamali.
        kaynaklar.sort(key=lambda kaynak: -kaynak.clicks)

        kalan = sum(adet for _, adet in hostlar[MAX_SOURCES:])
        if kalan:
            kaynaklar.append(
                ReferrerSource(kind=ReferrerKind.OTHER, clicks=kalan)
            )

        return ReferrerBreakdown(
            days=days,
            start_date=baslangic_gun,
            end_date=bugun,
            total_clicks=sum(kaynak.clicks for kaynak in kaynaklar),
            sources=kaynaklar,
        )

"""Pano ve analytics sayfasinin verisini hazirlar."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from models import EVENT_LINK_CLICK, EVENT_PROFILE_VIEW, User
from repositories.analytics.analytics_event_repository import (
    AnalyticsEventRepository,
)
from repositories.link.link_repository import LinkRepository
from services.analytics.analytics_dto import (
    AnalyticsDayPoint,
    AnalyticsSummary,
    AnalyticsTimeseries,
    BestTimes,
    HourBucket,
    LinkClickStat,
    LinkDayPoint,
    LinkTimeseries,
    LinkTimeseriesResponse,
    ReferrerBreakdown,
    ReferrerKind,
    ReferrerSource,
    WeekdayBucket,
)
from utils.time_utils import utcnow

# Ucun kabul ettigi araligin ust siniri. Uzun araliklar hem sorguyu hem de
# grafigi anlamsiz derecede yogunlastiriyor; gerekirse aylik bir uc eklenir.
MAX_DAYS = 90


@dataclass(frozen=True)
class Aralik:
    """Cozulmus tarih araligi; butun analytics uclari bunu kullaniyor.

    NEDEN AYRI BIR NESNE: dort uc de ayni araligi hesapliyordu ve her biri
    `days`i ayri ayri sinirliyordu. Serbest tarih araligi eklenince ayni
    dogrulamayi dort yerde tekrarlamak, birinde unutuldugunda yalnizca o
    ucun sinirsiz calismasi demekti. Aralik bir kez kuruluyor, dogrulama
    tek yerde.
    """

    days: int
    start_date: date
    end_date: date
    #: Ilk gunun basi (UTC), dahil.
    baslangic: datetime
    #: Son gunun ertesinin basi (UTC), HARIC. Gun sonunu 23:59:59 diye
    #: yazmak mikrosaniyelik olaylari disarida birakirdi.
    bitis: datetime


def aralik_kur(
    days: int | None = None,
    start: date | None = None,
    end: date | None = None,
) -> Aralik:
    """Ya son `days` gunu ya da verilen `start`-`end` araligini cozer.

    Iki ucu da dahil. Gunler UTC'ye gore ayriliyor -- olaylar da UTC
    saklaniyor, dolayisiyla gun sinirlari tutarli.

    Gecersiz girdide ValueError atiyor; cagiran uc bunu 422'ye ceviriyor.
    """
    if (start is None) != (end is None):
        # Tek basina bir ucun ne demek oldugu belirsiz: "start'tan bugune"
        # mi, "end'e kadar days gun" mu? Tahmin etmek yerine reddediyoruz.
        raise ValueError("start ve end birlikte verilmeli")

    if start is not None and end is not None:
        if start > end:
            raise ValueError("start, end'den sonra olamaz")
        gun_sayisi = (end - start).days + 1
        if gun_sayisi > MAX_DAYS:
            raise ValueError(f"Aralik en fazla {MAX_DAYS} gun olabilir")
        ilk_gun, son_gun = start, end
    else:
        gun_sayisi = max(1, min(days or 7, MAX_DAYS))
        son_gun = utcnow().date()
        ilk_gun = son_gun - timedelta(days=gun_sayisi - 1)

    return Aralik(
        days=gun_sayisi,
        start_date=ilk_gun,
        end_date=son_gun,
        baslangic=datetime.combine(ilk_gun, datetime.min.time(), tzinfo=UTC),
        bitis=datetime.combine(
            son_gun + timedelta(days=1), datetime.min.time(), tzinfo=UTC
        ),
    )


# Kaynak listesinde ayri satir olarak gosterilecek en fazla host sayisi;
# kalanlar tek bir "diger" satirinda toplaniyor. Uzun kuyruk panoda okunur
# bir sey anlatmiyor, yalnizca listeyi uzatiyor.
MAX_SOURCES = 8

# Zirveyi bir cikarim olarak sunmak icin gereken en az tiklama.
#
# Uc tiklamayla "en iyi gunun sali" demek, uc para atisina bakip yazi
# gelme egilimi oldugunu iddia etmek gibi. Bu esigin altinda dagilim yine
# donuyor ama enough_data false ve arayuz iddiada bulunmuyor.
MIN_CLICKS_FOR_PEAK = 20


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

    async def get_timeseries(self, user: User, aralik: Aralik) -> AnalyticsTimeseries:
        """Son `days` gunun gunluk tiklama ve profil goruntulenme sayilari.

        Gunler UTC'ye gore ayriliyor ve bugun dahil. Olay olmayan gunler de
        sifir degerlerle donuyor.
        """
        days, baslangic_gun, bugun = aralik.days, aralik.start_date, aralik.end_date

        satirlar = (
            await self.event_repository.daily_counts(
                user.id, aralik.baslangic, aralik.bitis
            )
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
        self, user: User, aralik: Aralik
    ) -> LinkTimeseriesResponse:
        """Her linkin secili aralikteki gunluk tiklama egrisi.

        Aralikta hic tiklanmayan linkler de listede, sifir degerlerle.
        Siralama: aralik icindeki tiklamaya gore azalan, esitlikte linkin
        kendi sirasina (order_index) gore -- boylece hicbir tiklama
        yokken liste herkese acik sayfadaki sirayi izliyor.
        """
        days, baslangic_gun, bugun = aralik.days, aralik.start_date, aralik.end_date

        links = await self.link_repository.get_links_by_user(
            user.id, include_inactive=True
        )

        satirlar = (
            await self.event_repository.daily_link_click_counts(
                user.id, aralik.baslangic, aralik.bitis
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

        gunler = [baslangic_gun + timedelta(days=gecen) for gecen in range(days)]

        seriler = []
        for link in links:
            link_sayaclari = sayaclar.get(link.id, {})
            noktalar = [
                LinkDayPoint(date=gun, clicks=link_sayaclari.get(gun.isoformat(), 0))
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

    async def get_referrers(self, user: User, aralik: Aralik) -> ReferrerBreakdown:
        """Secili aralikta tiklamalarin hangi siteden geldigi.

        Hicbir kaynagi olmayan bir aralik icin bos liste doner; cagiran taraf
        "henuz veri yok" durumunu sources'in bosluguyla ayirt edebiliyor.

        Dogrudan gelen tiklamalar ayri bir satir olarak listede: onlari
        gizlemek toplami tutarsiz gosterirdi ve "trafigimin ucte ikisini
        nereden geldigini bilmiyorum" da bir bilgi.
        """
        days, baslangic_gun, bugun = aralik.days, aralik.start_date, aralik.end_date

        satirlar = (
            await self.event_repository.referrer_counts(
                user.id, aralik.baslangic, aralik.bitis
            )
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
            kaynaklar.append(ReferrerSource(kind=ReferrerKind.DIRECT, clicks=dogrudan))

        # Dogrudan satiri da siralamaya giriyor: cogu sitede en buyuk pay
        # onda ve listenin ortasinda kaybolmamali.
        kaynaklar.sort(key=lambda kaynak: -kaynak.clicks)

        kalan = sum(adet for _, adet in hostlar[MAX_SOURCES:])
        if kalan:
            kaynaklar.append(ReferrerSource(kind=ReferrerKind.OTHER, clicks=kalan))

        return ReferrerBreakdown(
            days=days,
            start_date=baslangic_gun,
            end_date=bugun,
            total_clicks=sum(kaynak.clicks for kaynak in kaynaklar),
            sources=kaynaklar,
        )

    async def get_best_times(
        self, user: User, aralik: Aralik, tz_name: str = "UTC"
    ) -> BestTimes:
        """Tiklamalarin haftaguno ve saate dagilimi.

        Saat dilimi cevrimi burada, SQL'de degil: IANA saat dilimiyle
        gruplama PostgreSQL'e ozgu olurdu ve testler SQLite'ta kosuyor.
        Repository (gun, saat, adet) uclulerini UTC'ye gore donduruyor;
        her kutunun ortasi degil basi kullanicinin saat dilimine
        ceviriliyor. Bir saatlik kutu cevrildiginde de bir saatlik kutu
        kaliyor, dolayisiyla toplamlar korunuyor.

        zoneinfo kullanildigi icin yaz saati gecisleri de dogru: Mart'ta
        saatin ileri alindigi gun, o gunun kutulari kaymis haliyle
        sayiliyor.
        """
        days, baslangic_gun, bugun = aralik.days, aralik.start_date, aralik.end_date
        dilim = ZoneInfo(tz_name)

        satirlar = (
            await self.event_repository.hourly_click_counts(
                user.id, aralik.baslangic, aralik.bitis
            )
            if self.event_repository
            else []
        )

        gun_sayaci = [0] * 7
        saat_sayaci = [0] * 24

        for gun_metni, saat, adet in satirlar:
            yil, ay, gun = (int(parca) for parca in gun_metni.split("-"))
            utc_an = datetime(yil, ay, gun, saat, tzinfo=UTC)
            yerel = utc_an.astimezone(dilim)
            gun_sayaci[yerel.weekday()] += adet
            saat_sayaci[yerel.hour] += adet

        toplam = sum(gun_sayaci)

        return BestTimes(
            days=days,
            start_date=baslangic_gun,
            end_date=bugun,
            timezone=tz_name,
            total_clicks=toplam,
            by_weekday=[
                WeekdayBucket(weekday=indeks, clicks=adet)
                for indeks, adet in enumerate(gun_sayaci)
            ],
            by_hour=[
                HourBucket(hour=indeks, clicks=adet)
                for indeks, adet in enumerate(saat_sayaci)
            ],
            peak_weekday=_zirve(gun_sayaci),
            peak_hour=_zirve(saat_sayaci),
            enough_data=toplam >= MIN_CLICKS_FOR_PEAK,
        )


def _zirve(sayaclar: list[int]) -> int | None:
    """En cok tiklama alan kutunun indeksi; hic tiklama yoksa None.

    Esitlikte ilk kutu kazaniyor. Bu, "ilk gun/saat daha iyi" demek degil
    -- esitligi bozmanin veriye dayali bir yolu yok ve rastgele secmek
    ardisik isteklerde farkli cevap verirdi.
    """
    if not any(sayaclar):
        return None
    return max(range(len(sayaclar)), key=lambda indeks: sayaclar[indeks])

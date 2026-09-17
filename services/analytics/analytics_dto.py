"""Pano ve analytics sayfasinin okudugu ozet modeller."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class LinkClickStat(BaseModel):
    """Tek bir linkin tiklanma istatistigi."""

    id: int
    title: str
    url: str
    click_count: int
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AnalyticsSummary(BaseModel):
    """Kullanicinin toplam istatistikleri.

    Onceki hali tipsiz bir dict donuyordu: OpenAPI semasinda alanlar
    gorunmuyor ve frontend'in beklentisiyle sessizce ayrisabiliyordu.
    """

    username: str
    profile_url_path: str

    total_links: int
    active_links: int
    total_clicks: int
    profile_view_count: int

    # Tiklanmaya gore azalan sirada; pano "en cok tiklananlar" listesini
    # bunun basindan aliyor.
    links: list[LinkClickStat]


class AnalyticsDayPoint(BaseModel):
    """Bir gunun toplamlari."""

    date: date
    clicks: int
    profile_views: int


class AnalyticsTimeseries(BaseModel):
    """Gunluk zaman serisi.

    Olaysiz gunler de listede yer aliyor (sifir degerlerle): grafigi cizen
    taraf eksik gunleri kendisi tamamlamak zorunda kalmasin, arada bosluk
    olusmasin.

    DIKKAT: `total_clicks` ve `total_profile_views` yalnizca bu araligi
    kapsiyor; AnalyticsSummary'deki toplamlar hesabin tamamini sayiyor ve
    ikisi birbirini tutmayabilir. Olay kaydi sonradan eklendigi icin,
    ozetteki toplamlarin bir kisminin hicbir olay karsiligi yok.
    """

    days: int
    start_date: date
    end_date: date
    total_clicks: int
    total_profile_views: int
    points: list[AnalyticsDayPoint]


class LinkDayPoint(BaseModel):
    """Bir linkin bir gunku tiklanma sayisi."""

    date: date
    clicks: int


class LinkTimeseries(BaseModel):
    """Tek bir linkin secili aralikteki gunluk egrisi."""

    id: int
    title: str
    url: str
    is_active: bool

    # Yalnizca secili araligi kapsiyor; LinkClickStat.click_count ise linkin
    # tum gecmisini. Ikisi ayni sayi degil.
    total_clicks: int
    points: list[LinkDayPoint]


class LinkTimeseriesResponse(BaseModel):
    """Kullanicinin butun linkleri, secili aralikteki egrileriyle.

    Aralikta hic tiklanmayan linkler de listede: "bu link ise yaramadi"
    bilgisi de bir bilgi ve liste herkese acik sayfadakiyle ayni linkleri
    gostermeli.

    DIKKAT: Silinmis bir linke ait tiklamalar burada gorunmuyor (olay satiri
    duruyor ama artik bir linke baglanamiyor); genel zaman serisinde
    sayilmaya devam ediyorlar. Bu yuzden buradaki toplamlarin toplami,
    AnalyticsTimeseries.total_clicks'ten kucuk olabilir.
    """

    days: int
    start_date: date
    end_date: date
    links: list[LinkTimeseries]


class ReferrerKind(StrEnum):
    """Bir kaynak satirinin turu."""

    # Gercek bir dis site; `host` dolu.
    HOST = "host"
    # Dis bir referrer yok: adres cubuguna yazilmis, referrer'i gizleyen bir
    # uygulamadan gelinmis ya da site ici gezinme olmus.
    DIRECT = "direct"
    # Listeye sigmayan kaynaklarin toplami.
    OTHER = "other"


class ReferrerSource(BaseModel):
    """Tek bir trafik kaynagi ve bu araliktaki tiklama sayisi."""

    kind: ReferrerKind
    # Yalnizca kind == HOST iken dolu; "instagram.com" gibi.
    host: str | None = None
    clicks: int


class ReferrerBreakdown(BaseModel):
    """Secili aralikta tiklamalarin kaynaklara dagilimi.

    Siralama tiklamaya gore azalan; OTHER varsa her zaman sonda.

    DIKKAT: `total_clicks` yalnizca bu araligi ve yalnizca olay kaydi
    baslatildiktan sonraki tiklamalari kapsiyor. Referrer kolonu olay
    tablosundan da sonra eklendi: arada kalan tiklamalarin kaynagi hicbir
    zaman bilinmeyecek ve DIRECT sayiliyorlar.
    """

    days: int
    start_date: date
    end_date: date
    total_clicks: int
    sources: list[ReferrerSource]


class WeekdayBucket(BaseModel):
    """Bir haftagununun toplam tiklamasi."""

    # 0 = Pazartesi ... 6 = Pazar (datetime.weekday ile ayni).
    weekday: int
    clicks: int


class HourBucket(BaseModel):
    """Bir saatin toplam tiklamasi."""

    # 0-23, istekte verilen saat diliminde.
    hour: int
    clicks: int


class BestTimes(BaseModel):
    """Tiklamalarin haftaguno ve saate dagilimi.

    NEDEN SAAT DILIMI ISTEKTE: Olaylar UTC saklaniyor. "En cok tiklama saat
    14'te" bilgisi, kullanicinin kendi saatine cevrilmeden hicbir sey
    anlatmiyor -- Istanbul'da 17, Los Angeles'ta 06 demek. Cevrim sunucuda
    yapiliyor ki yaz saati gecisleri de dogru olsun.

    DIKKAT: `peak_weekday` ve `peak_hour` yalnizca en cok tiklama alan
    kutunun adi; az veriyle bunlar gurultu. `enough_data` tam bunun icin:
    false iken arayuz "en iyi gunun sali" gibi bir iddiada bulunmamali.
    """

    days: int
    start_date: date
    end_date: date
    # Istekte verilen IANA saat dilimi; verilmediyse "UTC".
    timezone: str

    total_clicks: int
    # Her zaman 7 ve 24 eleman; bos kutular sifirla doluyor ki cagiran
    # taraf eksik gunleri/saatleri kendisi tamamlamak zorunda kalmasin.
    by_weekday: list[WeekdayBucket]
    by_hour: list[HourBucket]

    peak_weekday: int | None
    peak_hour: int | None
    # Zirveyi bir cikarim olarak sunmak icin yeterli tiklama var mi?
    enough_data: bool

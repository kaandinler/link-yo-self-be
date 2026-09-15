"""Pano ve analytics sayfasinin okudugu ozet modeller."""

from datetime import date

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

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

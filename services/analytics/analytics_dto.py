"""Pano ve analytics sayfasinin okudugu ozet modeller."""

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

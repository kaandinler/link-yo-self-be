"""Pano ve analytics sayfasinin verisini hazirlar."""

from datetime import datetime, timedelta, timezone

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
)

# Ucun kabul ettigi araligin ust siniri. Uzun araliklar hem sorguyu hem de
# grafigi anlamsiz derecede yogunlastiriyor; gerekirse aylik bir uc eklenir.
MAX_DAYS = 90


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

    async def get_timeseries(self, user: User, days: int) -> AnalyticsTimeseries:
        """Son `days` gunun gunluk tiklama ve profil goruntulenme sayilari.

        Gunler UTC'ye gore ayriliyor ve bugun dahil. Olay olmayan gunler de
        sifir degerlerle donuyor.
        """
        days = max(1, min(days, MAX_DAYS))

        bugun = datetime.now(timezone.utc).date()
        baslangic_gun = bugun - timedelta(days=days - 1)
        # Gun basindan itibaren: sorgu gunun tamamini kapsamali.
        baslangic = datetime.combine(
            baslangic_gun, datetime.min.time(), tzinfo=timezone.utc
        )

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

"""Pano ve analytics sayfasinin verisini hazirlar."""

from models import User
from repositories.link.link_repository import LinkRepository
from services.analytics.analytics_dto import AnalyticsSummary, LinkClickStat


class AnalyticsService:
    def __init__(self, link_repo: LinkRepository):
        self.link_repository = link_repo

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

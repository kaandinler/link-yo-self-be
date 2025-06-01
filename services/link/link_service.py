# services/link/link_service.py

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_service import BaseService
from core.exceptions import NotFoundException, PermissionDeniedException
from models import Link, User
from repositories.link.link_repository import LinkRepository
from services.link.link_service_dto import LinkCreate, LinkUpdate, LinkRead, LinkReorderRequest


class LinkService(BaseService):
    def __init__(self, link_repo: LinkRepository):
        super().__init__(link_repo)
        self.repository = link_repo

    async def create_link(self, user_id: int, link_data: LinkCreate) -> Link:
        """Kullanıcı için yeni link oluşturur"""
        # Yeni linkin sıra numarasını belirle (son sıra + 1)
        max_order = await self.repository.get_max_order_for_user(user_id)
        order_index = (max_order or 0) + 1

        link = Link(
            user_id=user_id,
            title=link_data.title,
            url=link_data.url,
            description=link_data.description,
            icon_url=link_data.icon_url,
            background_color=link_data.background_color,
            text_color=link_data.text_color,
            border_radius=link_data.border_radius or 8,
            is_active=link_data.is_active if link_data.is_active is not None else True,
            order_index=order_index
        )

        return await self.repository.create_link(link)

    async def get_user_links(self, user_id: int, include_inactive: bool = False) -> List[Link]:
        """Kullanıcının linklerini sıralı şekilde getirir"""
        return await self.repository.get_links_by_user(user_id, include_inactive)

    async def get_link_by_id(self, link_id: int, user_id: int) -> Link:
        """Link ID'si ile link getirir ve kullanıcı yetkisini kontrol eder"""
        link = await self.repository.get_by_id(link_id)
        if not link:
            raise NotFoundException(f"Link not found: {link_id}")

        if link.user_id != user_id:
            raise PermissionDeniedException("You don't have permission to access this link")

        return link

    async def update_link(self, link_id: int, user_id: int, link_data: LinkUpdate) -> Link:
        """Link günceller, kullanıcı yetkisini kontrol eder"""
        link = await self.get_link_by_id(link_id, user_id)

        # Sadece None olmayan alanları güncelle
        update_data = link_data.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(link, key, value)

        return await self.repository.update_link(link)

    async def delete_link(self, link_id: int, user_id: int) -> None:
        """Link siler, kullanıcı yetkisini kontrol eder"""
        link = await self.get_link_by_id(link_id, user_id)
        await self.repository.delete_link(link)

    async def reorder_links(self, user_id: int, reorder_data: LinkReorderRequest) -> List[Link]:
        """Kullanıcının linklerini yeniden sıralar"""
        # Kullanıcının tüm linklerinin bu listede olduğunu kontrol et
        user_links = await self.repository.get_links_by_user(user_id, include_inactive=True)
        user_link_ids = {link.id for link in user_links}
        request_link_ids = set(reorder_data.link_ids)

        if user_link_ids != request_link_ids:
            raise PermissionDeniedException("Invalid link IDs provided")

        # Sıralamayı güncelle
        await self.repository.update_link_orders(user_id, reorder_data.link_ids)

        # Güncellenmiş linkleri döndür
        return await self.repository.get_links_by_user(user_id, include_inactive=True)

    async def increment_click_count(self, link_id: int) -> Link:
        """Link tıklanma sayısını artırır (Analytics için)"""
        link = await self.repository.get_by_id(link_id)
        if not link:
            raise NotFoundException(f"Link not found: {link_id}")

        link.click_count += 1
        return await self.repository.update_link(link)

    async def get_user_analytics(self, user_id: int) -> dict:
        """Kullanıcının link analytics verilerini getirir"""
        links = await self.repository.get_links_by_user(user_id, include_inactive=True)

        total_clicks = sum(link.click_count for link in links)
        active_links = len([link for link in links if link.is_active])

        return {
            "total_links": len(links),
            "active_links": active_links,
            "total_clicks": total_clicks,
            "links": [
                {
                    "id": link.id,
                    "title": link.title,
                    "url": link.url,
                    "click_count": link.click_count,
                    "is_active": link.is_active
                }
                for link in sorted(links, key=lambda x: x.click_count, reverse=True)
            ]
        }

    async def toggle_link_status(self, link_id: int, user_id: int) -> Link:
        """Link'in aktif/pasif durumunu değiştirir"""
        link = await self.get_link_by_id(link_id, user_id)
        link.is_active = not link.is_active
        return await self.repository.update_link(link)
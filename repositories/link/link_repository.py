# repositories/link/link_repository.py

from typing import List, Optional
from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_repository import BaseRepository
from models import Link


class LinkRepository(BaseRepository[Link]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = Link

    async def create_link(self, link: Link) -> Link:
        """Yeni link oluşturur"""
        return await self.create(link)

    async def update_link(self, link: Link) -> Link:
        """Link günceller"""
        return await self.update(link)

    async def delete_link(self, link: Link) -> None:
        """Link siler"""
        await self.delete(link)

    async def get_links_by_user(self, user_id: int, include_inactive: bool = False) -> List[Link]:
        """Kullanıcının linklerini order_index'e göre sıralı şekilde getirir"""

        async def _get_links(session: AsyncSession, user_id: int, include_inactive: bool) -> List[Link]:
            query = select(Link).where(Link.user_id == user_id)

            if not include_inactive:
                query = query.where(Link.is_active == True)

            # is_deleted = False kontrolü ekleyelim (soft delete için)
            query = query.where(Link.is_deleted == False)
            query = query.order_by(Link.order_index.asc())

            result = await session.execute(query)
            return result.scalars().all()

        return await self.execute_query(_get_links, user_id, include_inactive, transactional=False)

    async def get_max_order_for_user(self, user_id: int) -> Optional[int]:
        """Kullanıcının linklerinin maksimum order değerini getirir"""

        async def _get_max_order(session: AsyncSession, user_id: int) -> Optional[int]:
            query = select(func.max(Link.order_index)).where(
                and_(Link.user_id == user_id, Link.is_deleted == False)
            )
            result = await session.execute(query)
            return result.scalar()

        return await self.execute_query(_get_max_order, user_id, transactional=False)

    async def update_link_orders(self, user_id: int, ordered_link_ids: List[int]) -> None:
        """Kullanıcının linklerinin sırasını günceller"""

        async def _update_orders(session: AsyncSession, user_id: int, ordered_link_ids: List[int]) -> None:
            # Her link ID için yeni order_index değerini hesapla ve güncelle
            for index, link_id in enumerate(ordered_link_ids):
                await session.execute(
                    update(Link)
                    .where(and_(Link.id == link_id, Link.user_id == user_id))
                    .values(order_index=index + 1)
                )

            await session.flush()

        await self.execute_query(_update_orders, user_id, ordered_link_ids, transactional=True)

    async def get_public_links(self, user_id: int) -> List[Link]:
        """Kullanıcının public sayfası için aktif linklerini getirir"""

        async def _get_public_links(session: AsyncSession, user_id: int) -> List[Link]:
            query = select(Link).where(
                and_(
                    Link.user_id == user_id,
                    Link.is_active == True,
                    Link.is_deleted == False
                )
            ).order_by(Link.order_index.asc())

            result = await session.execute(query)
            return result.scalars().all()

        return await self.execute_query(_get_public_links, user_id, transactional=False)

    async def get_link_by_url(self, user_id: int, url: str) -> Optional[Link]:
        """Kullanıcının belirli URL'ye sahip linkini getirir (duplicate kontrolü için)"""

        async def _get_by_url(session: AsyncSession, user_id: int, url: str) -> Optional[Link]:
            query = select(Link).where(
                and_(
                    Link.user_id == user_id,
                    Link.url == url,
                    Link.is_deleted == False
                )
            )
            result = await session.execute(query)
            return result.scalars().first()

        return await self.execute_query(_get_by_url, user_id, url, transactional=False)

    async def search_links(self, user_id: int, search_term: str) -> List[Link]:
        """Kullanıcının linklerinde arama yapar"""

        async def _search_links(session: AsyncSession, user_id: int, search_term: str) -> List[Link]:
            query = select(Link).where(
                and_(
                    Link.user_id == user_id,
                    Link.is_deleted == False,
                    (Link.title.ilike(f"%{search_term}%") |
                     Link.description.ilike(f"%{search_term}%") |
                     Link.url.ilike(f"%{search_term}%"))
                )
            ).order_by(Link.order_index.asc())

            result = await session.execute(query)
            return result.scalars().all()

        return await self.execute_query(_search_links, user_id, search_term, transactional=False)

    async def get_links_by_status(self, user_id: int, is_active: bool) -> List[Link]:
        """Kullanıcının belirli durumda olan linklerini getirir"""

        async def _get_by_status(session: AsyncSession, user_id: int, is_active: bool) -> List[Link]:
            query = select(Link).where(
                and_(
                    Link.user_id == user_id,
                    Link.is_active == is_active,
                    Link.is_deleted == False
                )
            ).order_by(Link.order_index.asc())

            result = await session.execute(query)
            return result.scalars().all()

        return await self.execute_query(_get_by_status, user_id, is_active, transactional=False)
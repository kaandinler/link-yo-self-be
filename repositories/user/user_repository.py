from collections.abc import Awaitable, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.base_repository import BaseRepository
from models import User

# Listelemede siralanmasina izin verilen kolonlar. Beyaz liste sart: kolon adi
# istemciden geliyor, dogrudan getattr edilirse hashed_password gibi alanlara
# gore siralama (ve dolayli bilgi sizintisi) mumkun olurdu.
SORTABLE_FIELDS = frozenset(
    {
        "id",
        "username",
        "email",
        "first_name",
        "last_name",
        "is_admin",
        "created_at",
        "updated_at",
    }
)


class UserRepository(BaseRepository[User]):
    def __init__(self, session_factory):
        super().__init__(session_factory)
        self._model_type = User

    async def list_users(self, transactional: bool = False) -> Awaitable[Sequence[User]]:
        """Get all users with optional transaction control"""
        return await self.list_all(transactional=transactional)

    async def list_paginated(
        self,
        *,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
        is_admin: bool | None = None,
        order_by: str = "created_at",
        order: str = "desc",
        transactional: bool = False,
    ) -> tuple[Sequence[User], int]:
        """Admin listesi icin sayfalanmis kullanicilar ve toplam sayi.

        Silinmis kullanicilar listeye girmez. Toplam sayi ayni filtrelerle
        hesaplaniyor ki sayfa sayisi tutarli olsun.
        """

        async def _list_paginated(session: AsyncSession) -> tuple[Sequence[User], int]:
            filters = [User.is_deleted.is_(False)]

            if search:
                kalip = f"%{search.strip().lower()}%"
                filters.append(
                    or_(
                        func.lower(User.username).like(kalip),
                        func.lower(User.email).like(kalip),
                        func.lower(User.first_name).like(kalip),
                        func.lower(User.last_name).like(kalip),
                    )
                )

            if is_admin is not None:
                filters.append(User.is_admin.is_(is_admin))

            kolon_adi = order_by if order_by in SORTABLE_FIELDS else "created_at"
            kolon = getattr(User, kolon_adi)
            siralama = kolon.asc() if order.lower() == "asc" else kolon.desc()

            toplam = await session.scalar(
                select(func.count()).select_from(User).where(*filters)
            )

            result = await session.execute(
                select(User)
                .where(*filters)
                .order_by(siralama)
                .offset((page - 1) * limit)
                .limit(limit)
            )
            return result.scalars().all(), toplam or 0

        return await self.execute_query(_list_paginated, transactional=transactional)

    async def get_user(self, user_id: int, transactional: bool = False) -> User | None:
        """Get user by ID with optional transaction control"""
        return await self.get_by_id(user_id, transactional=transactional)

    async def get_by_username(
        self,
        username: str,
        transactional: bool = False,
        include_deleted: bool = False,
    ) -> User | None:
        """Kullanici adiyla kullaniciyi getirir.

        include_deleted yalnizca "bu kullanici adi musait mi" kontrolu icin
        True yapilmali: soft delete edilen kayit tabloda durdugu ve username
        UNIQUE oldugu icin, silinmis kaydi gormezden gelmek kaydi 500'e
        dusuren bir unique ihlaline yol acar. Kimlik dogrulama yolunda ise
        varsayilan (False) kalmali, aksi halde silinmis kullanici giris yapar.
        """

        async def _get_by_username(session: AsyncSession, username_: str) -> User | None:
            # links eager yuklenmeli: User.profile_completion_percentage bu
            # iliskiye eriseyor ve session kapandiktan sonra lazy load
            # DetachedInstanceError firlatir.
            query = (
                select(User)
                .options(selectinload(User.links))
                .where(User.username == username_)
            )
            if not include_deleted:
                query = query.where(User.is_deleted.is_(False))

            result = await session.execute(query)
            return result.scalars().first()

        # Use the execute_query helper for flexible transaction handling
        return await self.execute_query(_get_by_username, username, transactional=transactional)

    async def get_by_email(
        self,
        email: str,
        transactional: bool = False,
        include_deleted: bool = False,
    ) -> User | None:
        """E-posta ile kullaniciyi getirir (bkz. get_by_username notu)."""

        async def _get_by_email(session: AsyncSession, email_: str) -> User | None:
            query = (
                select(User)
                .options(selectinload(User.links))
                .where(User.email == email_)
            )
            if not include_deleted:
                query = query.where(User.is_deleted.is_(False))

            result = await session.execute(query)
            return result.scalars().first()

        # Use the execute_query helper for flexible transaction handling
        return await self.execute_query(_get_by_email, email, transactional=transactional)

    async def get_public_profile(
        self, username: str, transactional: bool = False
    ) -> User | None:
        """Public profil icin kullaniciyi linkleriyle birlikte getirir.

        Soft delete edilmis kullanicilar public sayfada gorunmez.
        """

        async def _get_public_profile(
            session: AsyncSession, username_: str
        ) -> User | None:
            result = await session.execute(
                select(User)
                .options(selectinload(User.links))
                .where(User.username == username_, User.is_deleted.is_(False))
            )
            return result.scalars().first()

        return await self.execute_query(
            _get_public_profile, username, transactional=transactional
        )

    async def create_user(self, user: User) -> User:
        """Create a new user (always transactional)"""
        return await self.create(user)

    async def update_user(self, user: User) -> User:
        """Update an existing user (always transactional)"""
        return await self.update(user)

    async def soft_delete_user(self, user: User) -> User:
        """Kullaniciyi siler ama satiri korur.

        Kayit fiziksel olarak silinmiyor: linkler ve tiklama istatistikleri
        cascade ile yok olurdu. Bunun yerine is_deleted isaretleniyor;
        kullanici adi/e-posta ise serbest birakilamaz (UNIQUE kisit) ve
        silinen kayit her yerde filtreleniyor.
        """
        user.is_deleted = True
        return await self.update(user)

    async def delete_user(self, user: User) -> None:
        """Delete a user (always transactional)"""
        await self.delete(user)

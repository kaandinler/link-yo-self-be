from collections.abc import Sequence

from core.auth.password import hash_password
from core.base_service import BaseService
from core.exceptions import (
    AlreadyExistsException,
    NotFoundException,
    ValidationException,
)
from models import User
from repositories.auth.refresh_token_repository import RefreshTokenRepository
from repositories.user.user_repository import UserRepository
from services.public.public_profile_dto import PublicLink, PublicProfile
from services.user.user_service_dto import UserCreateAdmin, UserUpdateAdmin


class UserService(BaseService):
    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository | None = None,
    ):
        super().__init__(user_repo)
        self.repository = user_repo
        # Kullanici silindiginde/pasiflestirildiginde acik oturumlarinin da
        # kapanmasi gerekiyor; access token kisa omurlu olsa da refresh token
        # gunlerce gecerli kaliyor.
        self.refresh_token_repository = refresh_token_repo

    async def list_users(self):
        return await self.list(User)

    async def list_users_paginated(
        self,
        *,
        page: int = 1,
        limit: int = 10,
        search: str | None = None,
        is_admin: bool | None = None,
        order_by: str = "created_at",
        order: str = "desc",
    ) -> tuple[Sequence[User], int]:
        """Admin listesi: (kullanicilar, toplam) doner."""
        return await self.repository.list_paginated(
            page=page,
            limit=limit,
            search=search,
            is_admin=is_admin,
            order_by=order_by,
            order=order,
        )

    async def get_user(self, user_id: int):
        user = await self.repository.get_by_id(user_id)
        # Soft delete edilmis kullanici yok sayilir; cagiranlar None'i 404'e
        # cevirdigi icin ayrica kontrol gerekmiyor.
        if user and user.is_deleted:
            return None
        return user

    async def create_user_as_admin(self, data: UserCreateAdmin) -> User:
        """Admin panelinden yeni kullanici olusturur."""
        await self._ensure_username_free(data.username)
        await self._ensure_email_free(str(data.email))

        user = User(
            username=data.username,
            email=str(data.email),
            hashed_password=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            is_admin=data.is_admin,
        )
        return await self.repository.create_user(user)

    async def update_user_as_admin(
        self, user_id: int, data: UserUpdateAdmin, acting_user: User
    ) -> User:
        """Admin panelinden kullanici gunceller.

        Yalnizca gonderilen alanlar degisir (PATCH). Admin kendi is_admin
        bayragini indiremez: son admin kendini yetkisizlestirirse panele bir
        daha kimse giremez.
        """
        user = await self.get_user(user_id)
        if not user:
            raise NotFoundException(f"User not found: {user_id}")

        degisenler = data.model_dump(exclude_unset=True)

        if "username" in degisenler and degisenler["username"] != user.username:
            await self._ensure_username_free(degisenler["username"])

        if "email" in degisenler:
            degisenler["email"] = str(degisenler["email"])
            if degisenler["email"] != user.email:
                await self._ensure_email_free(degisenler["email"])

        if "password" in degisenler:
            if degisenler["password"] is None:
                # Sifre "temizlenemez"; gonderilmek istenmiyorsa alan hic
                # gonderilmemeli.
                del degisenler["password"]
            else:
                user.hashed_password = hash_password(degisenler.pop("password"))

        if (
            "is_admin" in degisenler
            and degisenler["is_admin"] is False
            and user.id == acting_user.id
        ):
            raise ValidationException(
                detail="You cannot remove your own admin privileges"
            )

        for alan, deger in degisenler.items():
            setattr(user, alan, deger)

        return await self.repository.update_user(user)

    async def soft_delete_user(self, user_id: int, acting_user: User) -> None:
        """Kullaniciyi soft delete eder ve acik oturumlarini kapatir."""
        user = await self.get_user(user_id)
        if not user:
            raise NotFoundException(f"User not found: {user_id}")

        if user.id == acting_user.id:
            raise ValidationException(detail="You cannot delete your own account")

        await self.repository.soft_delete_user(user)

        # Silinen kullanicinin elindeki refresh token hala gecerli olsaydi
        # yeni access token uretip API'yi kullanmaya devam edebilirdi.
        if self.refresh_token_repository:
            await self.refresh_token_repository.revoke_all_user_tokens(user.id)

    async def _ensure_username_free(self, username: str) -> None:
        # include_deleted=True: silinen kayit tabloda kaliyor ve username
        # UNIQUE; gormezden gelirsek INSERT unique ihlaliyle 500 olurdu.
        mevcut = await self.repository.get_by_username(username, include_deleted=True)
        if mevcut:
            raise AlreadyExistsException(
                detail=f"This username already exists: {username}"
            )

    async def _ensure_email_free(self, email: str) -> None:
        mevcut = await self.repository.get_by_email(email, include_deleted=True)
        if mevcut:
            raise AlreadyExistsException(detail=f"This email already exists: {email}")

    async def get_by_username(self, username: str):
        return await self.repository.get_by_username(username)

    async def get_by_email(self, email: str):
        return await self.repository.get_by_email(email)

    async def create_user(self, user: User):
        return await self.repository.create_user(user)

    async def update_user(self, user: User):
        """Update user information"""
        return await self.repository.update(user)

    async def get_public_profile(self, username: str) -> PublicProfile:
        """Kullanicinin herkese acik link sayfasini olusturur.

        Sadece aktif ve silinmemis linkler, order_index sirasiyla doner.
        """
        user = await self.repository.get_public_profile(username.lower())
        if not user:
            raise NotFoundException(f"Profile not found: {username}")

        visible_links = sorted(
            (link for link in user.links if link.is_active and not link.is_deleted),
            key=lambda link: link.order_index,
        )

        return PublicProfile(
            username=user.username,
            display_name=user.profile_display_name,
            bio=user.bio,
            profile_image_url=user.profile_image_url,
            page_title=user.page_title,
            page_description=user.page_description,
            website=user.website,
            twitter_username=user.twitter_username,
            instagram_username=user.instagram_username,
            linkedin_username=user.linkedin_username,
            theme_color=user.theme_color,
            background_type=user.background_type,
            background_value=user.background_value,
            links=[PublicLink.model_validate(link) for link in visible_links],
        )

    async def check_username_availability(self, username: str) -> bool:
        """Kullanici adi musait mi (silinmis kayitlar da isgal eder)."""
        user = await self.repository.get_by_username(username, include_deleted=True)
        return user is None

    async def check_email_availability(self, email: str) -> bool:
        """E-posta musait mi (silinmis kayitlar da isgal eder)."""
        user = await self.repository.get_by_email(email, include_deleted=True)
        return user is None

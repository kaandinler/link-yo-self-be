from collections.abc import Sequence

from core.auth.password import hash_password, verify_password
from core.base_service import BaseService
from core.exceptions import (
    AlreadyExistsException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from models import EVENT_PROFILE_VIEW, User
from repositories.analytics.analytics_event_repository import (
    AnalyticsEventRepository,
)
from repositories.auth.refresh_token_repository import RefreshTokenRepository
from repositories.user.user_repository import UserRepository
from services.public.public_profile_dto import (
    PublicLink,
    PublicProfile,
    PublicProfileRef,
)
from services.user.user_service_dto import UserCreateAdmin, UserUpdateAdmin


class UserService(BaseService):
    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository | None = None,
        event_repo: AnalyticsEventRepository | None = None,
    ):
        super().__init__(user_repo)
        self.repository = user_repo
        # Kullanici silindiginde/pasiflestirildiginde acik oturumlarinin da
        # kapanmasi gerekiyor; access token kisa omurlu olsa da refresh token
        # gunlerce gecerli kaliyor.
        self.refresh_token_repository = refresh_token_repo
        # Opsiyonel: profil goruntuleme olayini kaydetmek icin.
        self.event_repository = event_repo

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
            # Admin kendi hesabini buradan degil, hesap ayarlarindan
            # (DELETE /users/me) sifre onayiyla kapatir.
            raise ValidationException(detail="You cannot delete your own account")

        await self._soft_delete(user)

    async def delete_own_account(self, user: User, password: str) -> None:
        """Kullanicinin kendi hesabini kapatmasi.

        Sifre dogrulamasi sart: geri alinamayan bir islem, calinmis bir oturum
        tek basina hesabi kapatabilmemeli.
        """
        if not verify_password(password, user.hashed_password):
            raise PermissionDeniedException(detail="Password is incorrect")

        # Son admin cikarsa yonetim paneline bir daha kimse giremez.
        if user.is_admin and await self.repository.count_admins() <= 1:
            raise ValidationException(
                detail="The last admin account cannot be deleted"
            )

        await self._soft_delete(user)

    async def _soft_delete(self, user: User) -> None:
        """Kaydi isaretler ve acik oturumlari kapatir."""
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

    async def get_public_profile(
        self, username: str, record_view: bool = True
    ) -> PublicProfile:
        """Kullanicinin herkese acik link sayfasini olusturur.

        Sadece aktif ve silinmemis linkler, order_index sirasiyla doner.

        record_view=True iken bu cagri ayni zamanda bir "goruntulenme"
        sayiliyor; sayac panoda gosteriliyor. Profil bulunamazsa sayac
        artmaz.
        """
        user = await self.repository.get_public_profile(username.lower())
        if not user:
            raise NotFoundException(f"Profile not found: {username}")

        if record_view:
            await self.repository.increment_profile_view(user.id)
            if self.event_repository:
                await self.event_repository.record(
                    user_id=user.id, event_type=EVENT_PROFILE_VIEW
                )

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

    async def list_public_profiles(
        self, limit: int, offset: int
    ) -> list[PublicProfileRef]:
        """Sitemap'e girecek profiller, kullanici adina gore sirali.

        Sayfalama cagiran tarafta: `limit`ten az satir gelmesi listenin
        bittigini gosteriyor, boylece ayri bir sayim sorgusu gerekmiyor.
        """
        satirlar = await self.repository.list_public_profiles(limit, offset)
        return [
            PublicProfileRef(username=username, last_modified=son_degisiklik)
            for username, son_degisiklik in satirlar
        ]

    async def check_username_availability(self, username: str) -> bool:
        """Kullanici adi musait mi (silinmis kayitlar da isgal eder)."""
        user = await self.repository.get_by_username(username, include_deleted=True)
        return user is None

    async def check_email_availability(self, email: str) -> bool:
        """E-posta musait mi (silinmis kayitlar da isgal eder)."""
        user = await self.repository.get_by_email(email, include_deleted=True)
        return user is None

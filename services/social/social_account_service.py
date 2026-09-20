# services/social/social_account_service.py


from core.base_service import BaseService
from core.exceptions import (
    AlreadyExistsException,
    NotFoundException,
    PermissionDeniedException,
    ValidationException,
)
from models import Platform, SocialAccount
from repositories.social.social_account_repository import SocialAccountRepository
from services.social.social_account_dto import (
    SocialAccountCreate,
    SocialAccountUpdate,
)


class SocialAccountService(BaseService):
    """Kullanicinin sosyal hesaplari.

    Modeller (Platform, SocialAccount) ilk migration'dan beri veritabaninda
    duruyordu ama hicbir servis, repository ya da uc onlara dokunmuyordu.
    Bu servis o boslugu dolduruyor.

    KAPSAM: her islem `user_id` ile sinirli. Baskasinin kaydina erismek
    403 -- links'teki `get_link_by_id` ile ayni kural, ayni sebeple:
    ayni sekilde davranan iki varligin iki farkli kurali olmasi, ikisine
    de bakan birinde hangisinin dogru oldugunu belirsizlestirir.
    """

    def __init__(self, social_account_repo: SocialAccountRepository):
        super().__init__(social_account_repo)
        self.repository = social_account_repo

    async def list_platforms(self) -> list[Platform]:
        """Secilebilir platformlar.

        Hesap acarken gecerli bir platform_id gerekiyor; istemcinin id
        listesini baska turlu ogrenmesinin yolu yok.
        """
        return await self.repository.list_platforms()

    async def get_accounts(self, user_id: int) -> list[SocialAccount]:
        return await self.repository.get_by_user(user_id)

    async def get_account(self, account_id: int, user_id: int) -> SocialAccount:
        hesap = await self.repository.get_by_id(account_id)
        if not hesap or hesap.is_deleted:
            raise NotFoundException(f"Social account not found: {account_id}")

        if hesap.user_id != user_id:
            raise PermissionDeniedException(
                "You don't have permission to access this social account"
            )

        return hesap

    async def create_account(
        self, user_id: int, data: SocialAccountCreate
    ) -> SocialAccount:
        await self._platform_var_mi(data.platform_id)
        await self._cakisma_yok_mu(user_id, data.platform_id, data.username)

        hesap = SocialAccount(
            user_id=user_id,
            platform_id=data.platform_id,
            username=data.username,
            profile_url=data.profile_url,
        )

        return await self.repository.create(hesap)

    async def update_account(
        self, account_id: int, user_id: int, data: SocialAccountUpdate
    ) -> SocialAccount:
        hesap = await self.get_account(account_id, user_id)

        guncellenecek = data.model_dump(exclude_unset=True, exclude_none=True)
        if not guncellenecek:
            raise ValidationException(detail="No fields to update")

        if "platform_id" in guncellenecek:
            await self._platform_var_mi(guncellenecek["platform_id"])

        # Tekillik kisiti uc alanin BIRLESIMINDE; biri degisse bile yeni
        # birlesimi kontrol etmek gerekiyor, degismeyenler mevcut kayittan
        # aliniyor.
        await self._cakisma_yok_mu(
            user_id,
            guncellenecek.get("platform_id", hesap.platform_id),
            guncellenecek.get("username", hesap.username),
            haric_tut_id=hesap.id,
        )

        for alan, deger in guncellenecek.items():
            setattr(hesap, alan, deger)

        return await self.repository.update(hesap)

    async def delete_account(self, account_id: int, user_id: int) -> None:
        hesap = await self.get_account(account_id, user_id)
        await self.repository.delete(hesap)

    async def _platform_var_mi(self, platform_id: int) -> None:
        """Olmayan platform 404.

        Kolon FOREIGN KEY; kontrol edilmezse IntegrityError patlar ve
        istemci 500 gorur.
        """
        if not await self.repository.get_platform(platform_id):
            raise NotFoundException(f"Platform not found: {platform_id}")

    async def _cakisma_yok_mu(
        self,
        user_id: int,
        platform_id: int,
        username: str,
        haric_tut_id: int | None = None,
    ) -> None:
        mevcut = await self.repository.get_duplicate(
            user_id, platform_id, username, haric_tut_id=haric_tut_id
        )
        if mevcut:
            raise AlreadyExistsException(
                detail="This account is already linked for that platform"
            )

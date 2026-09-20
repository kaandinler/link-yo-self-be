# services/page_settings/page_settings_service.py


from core.base_service import BaseService
from core.exceptions import ValidationException
from models import PageSettings
from repositories.page_settings.page_settings_repository import (
    PageSettingsRepository,
)
from services.page_settings.page_settings_dto import (
    PageSettingsRead,
    PageSettingsUpdate,
)


class PageSettingsService(BaseService):
    """Kullanicinin sayfa ayarlari (1:1).

    Model ilk migration'dan beri duruyordu ama hicbir uc ona
    dokunmuyordu. Bu servis onu bagliyor.

    SATIR TEMBEL OLUSUYOR: ayarlara hic dokunmamis kullanicinin satiri
    yok. Okuma bunu bir hata saymiyor, varsayilanlari donuyor; satir
    yalnizca ilk guncellemede yaziliyor. Alternatifi her kayitta bos bir
    satir acmakti -- kullanicilarin cogunlugu icin hicbir sey soylemeyen
    bir satir demek.
    """

    def __init__(self, page_settings_repo: PageSettingsRepository):
        super().__init__(page_settings_repo)
        self.repository = page_settings_repo

    async def get_settings(self, user_id: int) -> PageSettingsRead:
        ayarlar = await self.repository.get_by_user(user_id)
        if not ayarlar:
            # Satir yoksa varsayilanlar. Model uzerindeki default'larla
            # ayni olmali: adult_warning_enabled False, extra_settings bos.
            return PageSettingsRead(
                user_id=user_id,
                adult_warning_enabled=False,
                extra_settings=None,
            )

        return PageSettingsRead.model_validate(ayarlar)

    async def update_settings(
        self, user_id: int, data: PageSettingsUpdate
    ) -> PageSettingsRead:
        guncellenecek = data.model_dump(exclude_unset=True)
        if not guncellenecek:
            raise ValidationException(detail="No fields to update")

        ayarlar = await self.repository.get_by_user(user_id)

        if not ayarlar:
            ayarlar = PageSettings(
                user_id=user_id,
                # Verilmeyen alan varsayilaninda kalmali; model default'u
                # yalnizca INSERT sirasinda uygulandigi icin burada acikca
                # yaziliyor.
                adult_warning_enabled=guncellenecek.get("adult_warning_enabled", False),
                extra_settings=guncellenecek.get("extra_settings"),
            )
            olusan = await self.repository.create(ayarlar)
            return PageSettingsRead.model_validate(olusan)

        for alan, deger in guncellenecek.items():
            setattr(ayarlar, alan, deger)

        guncel = await self.repository.update(ayarlar)
        return PageSettingsRead.model_validate(guncel)

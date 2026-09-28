"""Platform yonetimi -- yalnizca admin.

NEDEN AYRI ROUTER: secim listesini okuyan uc
(GET /v1/social-accounts/platforms) kullaniciya ait ve oldugu yerde
kaliyor; burasi yonetim. Ikisini ayni dosyaya koymak, farkli yetki
seviyelerindeki uclari yan yana dizmek olurdu.

ONCEDEN YOKTU: 20 platform seed migration'iyla gelmisti ve yeni bir
platform eklemek yeni bir migration yazmak demekti (bkz.
alembic/versions/a7b8c9d0e1f2_seed_platforms.py).
"""

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from core.schemas.response import SuccessResponse
from deps import get_current_admin_user
from di.container import Container
from models import User
from services.social.social_account_dto import (
    PlatformAdminRead,
    PlatformCreate,
    PlatformRead,
    PlatformUpdate,
)
from services.social.social_account_service import SocialAccountService

router = APIRouter(tags=["platforms"])


@router.get("/", response_model=SuccessResponse[list[PlatformAdminRead]])
@inject
async def list_platforms(
    current_user: User = Depends(get_current_admin_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Butun platformlar, EMEKLIYE AYRILMISLAR DAHIL.

    Kullaniciya gosterilen liste (GET /v1/social-accounts/platforms)
    emeklileri filtreliyor. Burada goruluyorlar, cunku bir platformu
    geri getirmek isteyen yoneticinin once onu gorebilmesi gerekiyor.

    Her satirda `account_count`: emekliye ayirmadan once kac kullanicinin
    etkilenecegini gormek icin.
    """
    platformlar = await social_account_service.list_platforms_for_admin()

    return SuccessResponse.create(
        data=[
            PlatformAdminRead(
                id=platform.id,
                name=platform.name,
                display_name=platform.display_name,
                is_retired=platform.is_deleted,
                account_count=await social_account_service.platform_kullanim_sayisi(
                    platform.id
                ),
            )
            for platform in platformlar
        ],
        message="Platforms retrieved successfully",
    )


@router.post(
    "/",
    response_model=SuccessResponse[PlatformRead],
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_platform(
    payload: PlatformCreate,
    current_user: User = Depends(get_current_admin_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Yeni platform.

    Ayni adli EMEKLI bir kayit varsa yenisi acilmiyor, o geri
    getiriliyor -- eski satira bagli sosyal hesaplar yeniden gorunur
    olsun diye (bkz. service.create_platform).
    """
    platform = await social_account_service.create_platform(
        payload.name, payload.display_name
    )

    return SuccessResponse.create(
        data=PlatformRead.model_validate(platform),
        message="Platform created successfully",
    )


@router.patch("/{platform_id}", response_model=SuccessResponse[PlatformRead])
@inject
async def update_platform(
    platform_id: int,
    payload: PlatformUpdate,
    current_user: User = Depends(get_current_admin_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Yalnizca gosterim adi degisiyor; `name` sabit (bkz. PlatformUpdate)."""
    platform = await social_account_service.update_platform(
        platform_id, payload.display_name
    )

    return SuccessResponse.create(
        data=PlatformRead.model_validate(platform),
        message="Platform updated successfully",
    )


@router.delete("/{platform_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def retire_platform(
    platform_id: int,
    current_user: User = Depends(get_current_admin_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Platformu EMEKLIYE AYIRIR; satiri silmez.

    social_accounts.platform_id FOREIGN KEY ve ondelete CASCADE: satiri
    gercekten silmek o platformdaki butun kullanicilarin sosyal
    hesaplarini sessizce yok ederdi. Emekli platform secim listesinden
    cikiyor ama mevcut hesaplar yerinde kaliyor.
    """
    await social_account_service.retire_platform(platform_id)

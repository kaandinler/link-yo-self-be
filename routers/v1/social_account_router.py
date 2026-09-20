# routers/v1/social_account_router.py

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status

from core.schemas.response import SuccessResponse
from deps import get_current_user
from di.container import Container
from models import User
from services.social.social_account_dto import (
    PlatformRead,
    SocialAccountCreate,
    SocialAccountRead,
    SocialAccountUpdate,
)
from services.social.social_account_service import SocialAccountService

# Prefix disaridaki routers/social_account_router.py tarafindan veriliyor.
router = APIRouter(tags=["social-accounts"])


# DIKKAT - SIRA: "/platforms" rotasi "/{account_id}"den ONCE tanimli olmali.
# Sonra gelseydi FastAPI "platforms"i account_id olarak yorumlamaya calisir
# ve uc hicbir zaman ulasilamaz olurdu (422 donerdi).
@router.get("/platforms", response_model=SuccessResponse[list[PlatformRead]])
@inject
async def list_platforms(
    current_user: User = Depends(get_current_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Secilebilir platformlar.

    Token isteniyor: liste yalnizca hesap eklerken lazim ve hesap ekleyen
    zaten giris yapmis oluyor. Herkese acik profil sayfasi bu ucu
    cagirmiyor, platform adini kaydin kendisinden okuyor.
    """
    platforms = await social_account_service.list_platforms()
    return SuccessResponse.create(
        data=platforms,
        message="Platforms retrieved successfully",
    )


@router.post(
    "/",
    response_model=SuccessResponse[SocialAccountRead],
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_social_account(
    data: SocialAccountCreate,
    current_user: User = Depends(get_current_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Yeni sosyal hesap ekler."""
    hesap = await social_account_service.create_account(current_user.id, data)
    return SuccessResponse.create(
        data=hesap,
        message="Social account successfully created",
    )


@router.get("/", response_model=SuccessResponse[list[SocialAccountRead]])
@inject
async def get_my_social_accounts(
    current_user: User = Depends(get_current_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Kullanicinin sosyal hesaplarini getirir."""
    hesaplar = await social_account_service.get_accounts(current_user.id)
    return SuccessResponse.create(
        data=hesaplar,
        message="Social accounts retrieved successfully",
    )


@router.get("/{account_id}", response_model=SuccessResponse[SocialAccountRead])
@inject
async def get_social_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Belirli bir sosyal hesabi getirir."""
    hesap = await social_account_service.get_account(account_id, current_user.id)
    return SuccessResponse.create(
        data=hesap,
        message="Social account retrieved successfully",
    )


@router.put("/{account_id}", response_model=SuccessResponse[SocialAccountRead])
@inject
async def update_social_account(
    account_id: int,
    data: SocialAccountUpdate,
    current_user: User = Depends(get_current_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Sosyal hesabi gunceller."""
    hesap = await social_account_service.update_account(
        account_id, current_user.id, data
    )
    return SuccessResponse.create(
        data=hesap,
        message="Social account successfully updated",
    )


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_social_account(
    account_id: int,
    current_user: User = Depends(get_current_user),
    social_account_service: SocialAccountService = Depends(
        Provide[Container.social_account_service]
    ),
):
    """Sosyal hesabi siler."""
    await social_account_service.delete_account(account_id, current_user.id)

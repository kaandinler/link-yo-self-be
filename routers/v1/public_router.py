# routers/v1/public_router.py
"""Kimlik dogrulamasi gerektirmeyen public profil endpoint'leri."""

from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path

from core.schemas.response import SuccessResponse
from di.container import Container
from services.public.public_profile_dto import PublicProfile
from services.user.user_service import UserService

router = APIRouter(tags=["public"])


@router.get("/{username}", response_model=SuccessResponse[PublicProfile])
@inject
async def get_public_profile(
    username: Annotated[
        str, Path(min_length=3, max_length=30, description="Profil kullanici adi")
    ],
    user_service: Annotated[UserService, Depends(Provide[Container.user_service])],
):
    """Bir kullanicinin herkese acik link sayfasini doner.

    Token gerektirmez. Sadece aktif linkler ve gorunur profil alanlari doner;
    e-posta gibi hassas bilgiler bu yanitta yer almaz.
    """
    profile = await user_service.get_public_profile(username)
    return SuccessResponse.create(
        data=profile,
        message="Public profile retrieved successfully",
    )

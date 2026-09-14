
from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path, Query, status

from core.exceptions import NotFoundException
from core.schemas.response import BaseResponseModel, PaginatedResponseModel
from deps import get_current_admin_user, get_current_user
from di.container import Container
from services.user.user_service_dto import UserCreateAdmin, UserRead, UserUpdateAdmin

router = APIRouter(tags=["users"])


@router.get("/", response_model=PaginatedResponseModel[UserRead])
@inject
async def list_users(
    page: Annotated[int, Query(ge=1, description="1'den baslayan sayfa numarasi")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Sayfa basina kayit")] = 10,
    search: Annotated[
        str | None, Query(description="Kullanici adi, e-posta, ad veya soyadda arar")
    ] = None,
    is_admin: Annotated[bool | None, Query(description="Admin filtresi")] = None,
    order_by: Annotated[str, Query(description="Siralama alani")] = "created_at",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    current_user=Depends(get_current_admin_user),
    service=Depends(Provide[Container.user_service])
):
    """Admin kullanici listesi (sayfalanmis).

    Toplam kayit sayisi meta icinde doner; frontend "sonraki sayfa var mi"
    bilgisini buradan hesapliyor.
    """
    users, total = await service.list_users_paginated(
        page=page,
        limit=limit,
        search=search,
        is_admin=is_admin,
        order_by=order_by,
        order=order,
    )

    return PaginatedResponseModel(
        data=[UserRead.model_validate(user) for user in users],
        message="Users retrieved successfully",
        meta={
            "page": page,
            "limit": limit,
            "total": total,
            # Toplam sayfa sayisi yerine "daha var mi" bilgisi de veriliyor;
            # sonsuz kaydirma yapan liste bunu kullaniyor.
            "total_pages": (total + limit - 1) // limit,
            "has_next_page": page * limit < total,
        },
    )


@router.post(
    "/",
    response_model=BaseResponseModel[UserRead],
    status_code=status.HTTP_201_CREATED,
)
@inject
async def create_user(
    user_in: UserCreateAdmin,
    current_user=Depends(get_current_admin_user),
    service=Depends(Provide[Container.user_service])
):
    """Admin panelinden yeni kullanici olusturur."""
    user = await service.create_user_as_admin(user_in)
    return BaseResponseModel(
        data=UserRead.model_validate(user),
        message="User created successfully"
    )


# NOT: /me route'u /{user_id}'den ÖNCE tanımlanmalı, aksi halde FastAPI
# "me" değerini user_id path parametresi olarak yorumlayıp 422 döner.
@router.get('/me', response_model=BaseResponseModel[UserRead])
async def read_users_me(current_user=Depends(get_current_user)):
    # SQLAlchemy modeli direkt döndürmek yerine, Pydantic modeline dönüştürerek döndürüyoruz
    user_data = UserRead.model_validate(current_user)
    return BaseResponseModel(
        data=user_data,
        message="User profile retrieved successfully"
    )


@router.get("/{user_id}", response_model=BaseResponseModel[UserRead])
@inject
async def get_user(
    user_id: Annotated[int, Path(ge=1)],
    current_user=Depends(get_current_user),
    service=Depends(Provide[Container.user_service])
):
    user = await service.get_user(user_id)
    if not user:
        raise NotFoundException(f"User not found: {user_id}")
    return BaseResponseModel(
        data=UserRead.model_validate(user),
        message="User retrieved successfully"
    )


@router.patch("/{user_id}", response_model=BaseResponseModel[UserRead])
@inject
async def update_user(
    user_id: Annotated[int, Path(ge=1)],
    user_in: UserUpdateAdmin,
    current_user=Depends(get_current_admin_user),
    service=Depends(Provide[Container.user_service])
):
    """Kullaniciyi gunceller; yalnizca gonderilen alanlar degisir."""
    user = await service.update_user_as_admin(user_id, user_in, current_user)
    return BaseResponseModel(
        data=UserRead.model_validate(user),
        message="User updated successfully"
    )


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_user(
    user_id: Annotated[int, Path(ge=1)],
    current_user=Depends(get_current_admin_user),
    service=Depends(Provide[Container.user_service])
):
    """Kullaniciyi soft delete eder ve acik oturumlarini kapatir."""
    await service.soft_delete_user(user_id, current_user)

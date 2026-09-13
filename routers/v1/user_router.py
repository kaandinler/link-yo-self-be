
from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from core.exceptions import NotFoundException
from core.schemas.response import BaseResponseModel
from deps import get_current_admin_user, get_current_user
from di.container import Container
from services.user.user_service_dto import UserRead

router = APIRouter(tags=["users"])


@router.get("/", response_model=BaseResponseModel[list[UserRead]])
@inject
async def list_users(
    current_user=Depends(get_current_admin_user),
    service=Depends(Provide[Container.user_service])
):
    users = await service.list_users()
    return BaseResponseModel(
        data=users,
        message="Users retrieved successfully"
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
    user_id: int,
    current_user=Depends(get_current_user),
    service=Depends(Provide[Container.user_service])
):
    user = await service.get_user(user_id)
    if not user:
        raise NotFoundException(f"User not found: {user_id}")
    return BaseResponseModel(
        data=user,
        message="User retrieved successfully"
    )

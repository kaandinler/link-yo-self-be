from fastapi import APIRouter, Depends
from dependency_injector.wiring import Provide, inject
from typing import List

from deps import get_current_user, get_current_admin_user
from di.container import Container
from services.user.user_service_dto import UserRead
from core.schemas.response import BaseResponseModel
from core.exceptions import NotFoundException

router = APIRouter(tags=["users"])

@router.get("/", response_model=BaseResponseModel[List[UserRead]])
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


@router.get('/me', response_model=BaseResponseModel[UserRead])
async def read_users_me(current_user=Depends(get_current_user)):
    return BaseResponseModel(data=current_user)

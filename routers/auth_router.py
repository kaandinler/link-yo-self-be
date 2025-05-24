from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from core.auth.auth_service import AuthService
from core.exceptions import AlreadyExistsException, InvalidCredentialsException
from core.schemas.response import BaseResponseModel
from di.container import Container
from services.user.user_service import UserService
from services.user.user_service_dto import UserCreate, UserRead

router = APIRouter(prefix='/auth', tags=['auth'])


@router.post('/token', response_model=BaseResponseModel[dict])
@inject
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise InvalidCredentialsException

    access_token = auth_service.create_access_token({'sub': user.username})
    return {
        "data": {'access_token': access_token, 'token_type': 'bearer'},
        "message": "Giriş başarılı"
    }


@router.post("/register", response_model=BaseResponseModel[UserRead], status_code=status.HTTP_201_CREATED)
@inject
async def register(
        user_in: UserCreate,
        auth_service: AuthService = Depends(Provide[Container.auth_service,]),
        user_service: UserService = Depends(Provide[Container.user_service]),
):
    existing = await user_service.get_by_username(user_in.username)
    if existing:
        raise AlreadyExistsException(detail=f"Bu kullanıcı adı zaten alınmış: {user_in.username}")

    user = await auth_service.register_user(user_in)
    return {
        "data": user,
        "message": "Kullanıcı başarıyla oluşturuldu"
    }

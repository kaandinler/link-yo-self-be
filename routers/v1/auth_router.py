from dependency_injector.wiring import inject, Provide
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from core.auth.auth_service import AuthService
from core.exceptions import AlreadyExistsException
from core.schemas.response import BaseResponseModel
from deps import get_current_user
from di.container import Container
from services.auth.auth_service_dto import TokenResponse, TokenRefreshRequest
from services.user.user_service import UserService
from services.user.user_service_dto import UserRead, UserCreateMinimal

router = APIRouter(tags=['auth'])


@router.post('/token', response_model=BaseResponseModel[TokenResponse])
@inject
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    user = await auth_service.authenticate_user(form_data.username, form_data.password)

    # Access token ve refresh token oluştur
    access_token, refresh_token = await auth_service.create_tokens(user)

    return BaseResponseModel(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        ),
        message="Successfully logged in"
    )

@router.post('/refresh', response_model=BaseResponseModel[TokenResponse])
@inject
async def refresh_token(
        refresh_request: TokenRefreshRequest,
        auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    # Refresh token ile yeni access token oluştur
    access_token = await auth_service.refresh_access_token(refresh_request.refresh_token)

    return BaseResponseModel(
        data=TokenResponse(
            access_token=access_token,
            token_type="bearer"
        ),
        message="Token successfully refreshed"
    )

@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
@inject
async def logout(
    current_user=Depends(get_current_user),  # Token'dan user'ı al
    auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    """Kullanıcının tüm refresh token'larını geçersiz kılar"""
    # Kullanıcının tüm refresh token'larını iptal et
    await auth_service.revoke_all_user_tokens(current_user.id)
    return None


@router.post("/register", response_model=BaseResponseModel[UserRead], status_code=status.HTTP_201_CREATED)
@inject
async def register(
        user_in: UserCreateMinimal,
        auth_service: AuthService = Depends(Provide[Container.auth_service,]),
        user_service: UserService = Depends(Provide[Container.user_service]),
):
    existing_username = await user_service.get_by_username(user_in.username)
    if existing_username:
        raise AlreadyExistsException(detail=f"This username already exists: {user_in.username}")

    existing_email = await user_service.get_by_email(str(user_in.email))
    if existing_email:
        raise AlreadyExistsException(detail=f"This email already exists: {user_in.email}")

    user = await auth_service.register_user(user_in)
    return BaseResponseModel(
        data=user,
        message="User successfully registered"
    )


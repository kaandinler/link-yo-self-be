from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from core.auth.auth_service import AuthService
from core.exceptions import AlreadyExistsException
from core.schemas.response import BaseResponseModel
from deps import get_current_user
from di.container import Container
from services.auth.auth_service_dto import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenRefreshRequest,
    TokenResponse,
)
from services.user.user_service import UserService
from services.user.user_service_dto import UserCreateMinimal, UserRead

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


@router.post("/register", response_model=BaseResponseModel[UserRead], status_code=status.HTTP_201_CREATED)
@inject
async def register(
        user_in: UserCreateMinimal,
        auth_service: AuthService = Depends(Provide[Container.auth_service,]),
        user_service: UserService = Depends(Provide[Container.user_service]),
):
    # DIKKAT: get_by_username/get_by_email silinmis kayitlari filtreliyor
    # (silinmis kullanici giris yapamasin diye). Musaitlik kontrolu ise
    # silinmis kayitlari da gormeli: satir tabloda duruyor ve username/email
    # UNIQUE, aksi halde INSERT 500 ile patlardi.
    if not await user_service.check_username_availability(user_in.username):
        raise AlreadyExistsException(detail=f"This username already exists: {user_in.username}")

    if not await user_service.check_email_availability(str(user_in.email)):
        raise AlreadyExistsException(detail=f"This email already exists: {user_in.email}")

    user = await auth_service.register_user(user_in)
    return BaseResponseModel(
        data=user,
        message="User successfully registered"
    )



@router.post('/forgot-password', status_code=status.HTTP_204_NO_CONTENT)
@inject
async def forgot_password(
        request: ForgotPasswordRequest,
        auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    """Sifre sifirlama baglantisi gonderir.

    E-posta kayitli olmasa bile 204 doner. Farkli yanit vermek, bir adresin
    sistemde kayitli olup olmadigini ogrenmeye yarardi.
    """
    await auth_service.request_password_reset(str(request.email))


@router.post('/reset-password', status_code=status.HTTP_204_NO_CONTENT)
@inject
async def reset_password(
        request: ResetPasswordRequest,
        auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    """Token ile yeni sifreyi kaydeder ve acik oturumlari kapatir."""
    await auth_service.reset_password(request.token, request.password)


@router.post('/change-password', response_model=BaseResponseModel[TokenResponse])
@inject
async def change_password(
        request: ChangePasswordRequest,
        current_user=Depends(get_current_user),
        auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    """Giris yapmis kullanicinin kendi sifresini degistirmesi.

    Mevcut sifreyi dogrular, diger cihazlardaki oturumlari kapatir ve bu
    oturumun devam edebilmesi icin yeni token cifti doner.
    """
    access_token, refresh_token = await auth_service.change_password(
        current_user, request.current_password, request.new_password
    )

    return BaseResponseModel(
        data=TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        ),
        message="Password successfully changed"
    )


@router.post('/change-email', response_model=BaseResponseModel[UserRead])
@inject
async def change_email(
        request: ChangeEmailRequest,
        current_user=Depends(get_current_user),
        auth_service: AuthService = Depends(Provide[Container.auth_service])
):
    """Giris yapmis kullanicinin e-posta adresini degistirmesi.

    Sifre onayi ister; e-posta sifre sifirlama baglantisinin gittigi adres.
    """
    user = await auth_service.change_email(
        current_user, request.password, str(request.new_email)
    )

    return BaseResponseModel(
        data=UserRead.model_validate(user),
        message="Email successfully changed"
    )

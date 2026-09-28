from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request, status
from fastapi.security import OAuth2PasswordRequestForm

from core.auth.auth_service import AuthService
from core.exceptions import AlreadyExistsException, InvalidCredentialsException
from core.rate_limit import (
    GIRIS_HESAP,
    GIRIS_IP,
    KAYIT_IP,
    SIFIRLAMA_HESAP,
    SIFIRLAMA_IP,
    TOKEN_IP,
    YENIDEN_GONDER_KULLANICI,
    basarisizligi_isaretle,
    dogrula,
    say_ve_dogrula,
    say_ve_dogrula_hesap,
)
from core.schemas.response import BaseResponseModel
from deps import get_current_user
from di.container import Container
from services.auth.auth_service_dto import (
    ChangeEmailRequest,
    ChangePasswordRequest,
    EmailChangeRequested,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    TokenRefreshRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from services.user.user_service import UserService
from services.user.user_service_dto import UserCreateMinimal, UserRead

router = APIRouter(tags=["auth"])


@router.post("/token", response_model=BaseResponseModel[TokenResponse])
@inject
async def login(
    http_request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    """Giris.

    HIZ SINIRI YALNIZCA BASARISIZ DENEMELERI SAYIYOR. Once bakiliyor
    (`dogrula`), sonra yalnizca kimlik dogrulama dustuyse
    isaretleniyor. Her istegi saysaydik dogru sifreyle giren kullanici
    da kendi limitini yakar, sik giris yapan biri kendini disari
    kilitleyebilirdi.

    Iki katman birden: hesap basina (tek bir hesaba yonelen deneme) ve
    IP basina (cok sayida hesaba yayilan deneme).
    """
    await dogrula(http_request, form_data.username, "giris", GIRIS_IP, GIRIS_HESAP)

    try:
        user = await auth_service.authenticate_user(
            form_data.username, form_data.password
        )
    except InvalidCredentialsException:
        await basarisizligi_isaretle(
            http_request, form_data.username, "giris", GIRIS_IP, GIRIS_HESAP
        )
        raise

    # Access token ve refresh token oluştur
    access_token, refresh_token = await auth_service.create_tokens(user)

    return BaseResponseModel(
        data=TokenResponse(
            access_token=access_token, refresh_token=refresh_token, token_type="bearer"
        ),
        message="Successfully logged in",
    )


@router.post("/refresh", response_model=BaseResponseModel[TokenResponse])
@inject
async def refresh_token(
    refresh_request: TokenRefreshRequest,
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    # Refresh token ile yeni access token oluştur
    access_token = await auth_service.refresh_access_token(
        refresh_request.refresh_token
    )

    return BaseResponseModel(
        data=TokenResponse(access_token=access_token, token_type="bearer"),
        message="Token successfully refreshed",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def logout(
    current_user=Depends(get_current_user),  # Token'dan user'ı al
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    """Kullanıcının tüm refresh token'larını geçersiz kılar"""
    # Kullanıcının tüm refresh token'larını iptal et
    await auth_service.revoke_all_user_tokens(current_user.id)


@router.post(
    "/register",
    response_model=BaseResponseModel[UserRead],
    status_code=status.HTTP_201_CREATED,
)
@inject
async def register(
    http_request: Request,
    user_in: UserCreateMinimal,
    auth_service: AuthService = Depends(Provide[Container.auth_service,]),
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    # Kayitta henuz bir hesap yok, yani IP'den baska sinirlanacak bir
    # anahtar da yok.
    await say_ve_dogrula(http_request, "kayit", KAYIT_IP)

    # DIKKAT: get_by_username/get_by_email silinmis kayitlari filtreliyor
    # (silinmis kullanici giris yapamasin diye). Musaitlik kontrolu ise
    # silinmis kayitlari da gormeli: satir tabloda duruyor ve username/email
    # UNIQUE, aksi halde INSERT 500 ile patlardi.
    if not await user_service.check_username_availability(user_in.username):
        raise AlreadyExistsException(
            detail=f"This username already exists: {user_in.username}"
        )

    if not await user_service.check_email_availability(str(user_in.email)):
        raise AlreadyExistsException(
            detail=f"This email already exists: {user_in.email}"
        )

    user = await auth_service.register_user(user_in)
    return BaseResponseModel(data=user, message="User successfully registered")


@router.post("/forgot-password", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def forgot_password(
    http_request: Request,
    request: ForgotPasswordRequest,
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    """Sifre sifirlama baglantisi gonderir.

    E-posta kayitli olmasa bile 204 doner. Farkli yanit vermek, bir adresin
    sistemde kayitli olup olmadigini ogrenmeye yarardi.

    HIZ SINIRI HER ISTEGI SAYIYOR (giristen farkli olarak): bu ucta
    "basarili/basarisiz" diye bir sey yok, istegin yapilmis olmasi
    zaten bir e-posta demek. Adres basina sinir, saldirgan IP
    degistirse bile tek bir adrese bombardimani durduruyor.

    SIZDIRMIYOR: sayaclar cagiranin kendi istek sayisina bakiyor,
    adresin kayitli olup olmadigina degil.
    """
    await say_ve_dogrula(http_request, "sifirlama", SIFIRLAMA_IP)
    await say_ve_dogrula_hesap(str(request.email), "sifirlama", SIFIRLAMA_HESAP)

    await auth_service.request_password_reset(str(request.email))


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def reset_password(
    http_request: Request,
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    """Token ile yeni sifreyi kaydeder ve acik oturumlari kapatir."""
    await say_ve_dogrula(http_request, "token", TOKEN_IP)

    await auth_service.reset_password(request.token, request.password)


@router.post("/change-password", response_model=BaseResponseModel[TokenResponse])
@inject
async def change_password(
    request: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
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
            access_token=access_token, refresh_token=refresh_token, token_type="bearer"
        ),
        message="Password successfully changed",
    )


@router.post(
    "/change-email",
    response_model=BaseResponseModel[EmailChangeRequested],
    status_code=status.HTTP_202_ACCEPTED,
)
@inject
async def change_email(
    request: ChangeEmailRequest,
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    """E-posta adresi degistirme TALEBI.

    DIKKAT: Adres burada degismiyor (bu yuzden 202). Yeni adrese dogrulama
    baglantisi gonderiliyor; degisiklik ancak kullanici o baglantiya
    tikladiginda uygulaniyor. Aksi halde yanlis yazilan bir adres kullaniciyi
    sifre sifirlamadan -- tek kurtarma yolundan -- ederdi.
    """
    pending = await auth_service.request_email_change(
        current_user, request.password, str(request.new_email)
    )

    return BaseResponseModel(
        data=EmailChangeRequested(pending_email=pending),
        message="Confirmation link sent to the new address",
    )


@router.post("/verify-email", response_model=BaseResponseModel[UserRead])
@inject
async def verify_email(
    http_request: Request,
    request: VerifyEmailRequest,
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    """E-postadaki dogrulama baglantisini isler.

    Token bir adres degisikligine aitse adres burada uygulaniyor. Uc token
    istemiyor: kullanici baglantiya baska bir cihazdan/tarayicidan tiklamis
    olabilir.
    """
    await say_ve_dogrula(http_request, "token", TOKEN_IP)

    user = await auth_service.verify_email(request.token)

    return BaseResponseModel(
        data=UserRead.model_validate(user), message="Email successfully verified"
    )


@router.post(
    "/resend-verification", response_model=BaseResponseModel[EmailChangeRequested]
)
@inject
async def resend_verification(
    current_user=Depends(get_current_user),
    auth_service: AuthService = Depends(Provide[Container.auth_service]),
):
    """Dogrulama baglantisini yeniden gonderir.

    Onay bekleyen bir adres degisikligi varsa baglanti yine o adrese gider;
    yoksa kullanicinin mevcut adresine.
    """
    # Anahtar dogrudan kullanicinin kendisi: uc giris istiyor, yani
    # IP'ye gerek yok ve NAT arkasindaki baskalarini etkilemiyor.
    await say_ve_dogrula_hesap(
        str(current_user.id), "yeniden_gonder", YENIDEN_GONDER_KULLANICI
    )

    hedef = await auth_service.resend_verification_email(current_user)

    return BaseResponseModel(
        data=EmailChangeRequested(pending_email=hedef), message="Confirmation link sent"
    )

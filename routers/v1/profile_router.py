# routers/v1/profile_router.py

import logging

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Request
from starlette.concurrency import run_in_threadpool

# fastapi.UploadFile DEGIL: request.form() Starlette'in sinifini donduruyor ve
# FastAPI'ninki onun alt sinifi, yani isinstance kontrolu hep dusuyordu.
from starlette.datastructures import UploadFile

from core.exceptions import (
    LengthRequiredException,
    PayloadTooLargeException,
    ValidationException,
)
from core.rate_limit import AVATAR_KULLANICI, say_ve_dogrula_hesap
from core.schemas.response import SuccessResponse
from core.storage import Depo, avatar_anahtari
from deps import get_current_user
from di.container import Container
from models import User
from services.page_settings.page_settings_dto import (
    PageSettingsRead,
    PageSettingsUpdate,
)
from services.page_settings.page_settings_service import PageSettingsService
from services.user.avatar import GecersizGorsel, avatar_isle
from services.user.user_service import UserService
from services.user.user_service_dto import (
    OnboardingStatus,
    ProfileCompletionStep1,
    ProfileCompletionStep2,
    ProfileCompletionStep3,
    ProfileCompletionStep4,
    UserProfileUpdate,
    UserRead,
)
from settings import settings

logger = logging.getLogger(__name__)

# Prefix dışarıdaki routers/profile_router.py tarafından veriliyor (/profile),
# burada tekrar tanımlanırsa /api/v1/profile/profile/... oluşur.
router = APIRouter(tags=["profile"])


@router.get("/me", response_model=SuccessResponse[UserRead])
async def get_my_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return SuccessResponse.create(
        data=current_user, message="Profile retrieved successfully"
    )


@router.get("/onboarding-status", response_model=SuccessResponse[OnboardingStatus])
async def get_onboarding_status(current_user: User = Depends(get_current_user)):
    """Get user's onboarding status"""

    # Determine completed steps
    completed_steps = []
    next_step = 1

    # Step 1: Basic info
    if current_user.display_name or current_user.bio or current_user.profile_image_url:
        completed_steps.append(1)
        next_step = 2

    # Step 2: Page settings
    if current_user.page_title or current_user.website:
        completed_steps.append(2)
        next_step = 3

    # Step 3: Social media
    if (
        current_user.twitter_username
        or current_user.instagram_username
        or current_user.linkedin_username
    ):
        completed_steps.append(3)
        next_step = 4

    # Step 4: Theme
    if current_user.theme_color != "#1383eb" or current_user.background_type != "color":
        completed_steps.append(4)
        next_step = 5  # Completed

    # Define step titles
    step_titles = {
        1: "Complete Your Profile",
        2: "Set Up Your Page",
        3: "Add Social Links",
        4: "Customize Appearance",
        5: "Add Your First Links",
    }

    status = OnboardingStatus(
        step=next_step,
        completed_steps=completed_steps,
        profile_completion_percentage=current_user.profile_completion_percentage,
        next_step_title=step_titles.get(next_step),
        can_skip=True,
    )

    return SuccessResponse.create(data=status, message="Onboarding status retrieved")


@router.post("/complete-step-1", response_model=SuccessResponse[UserRead])
@inject
async def complete_profile_step_1(
    profile_data: ProfileCompletionStep1,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    """Complete profile step 1: Basic profile info"""

    # Update user with new data
    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user, message="Profile step 1 completed successfully"
    )


@router.post("/complete-step-2", response_model=SuccessResponse[UserRead])
@inject
async def complete_profile_step_2(
    profile_data: ProfileCompletionStep2,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    """Complete profile step 2: Page settings"""

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user, message="Profile step 2 completed successfully"
    )


@router.post("/complete-step-3", response_model=SuccessResponse[UserRead])
@inject
async def complete_profile_step_3(
    profile_data: ProfileCompletionStep3,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    """Complete profile step 3: Social media links"""

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user, message="Profile step 3 completed successfully"
    )


@router.post("/complete-step-4", response_model=SuccessResponse[UserRead])
@inject
async def complete_profile_step_4(
    profile_data: ProfileCompletionStep4,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    """Complete profile step 4: Theme & appearance"""

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user, message="Profile step 4 completed successfully"
    )


@router.post("/complete-onboarding", response_model=SuccessResponse[UserRead])
@inject
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    """Mark onboarding as completed"""

    current_user.onboarding_completed = True
    current_user.profile_completed = True

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Onboarding completed successfully! Welcome to LinkYoSelf!",
    )


@router.get("/page-settings", response_model=SuccessResponse[PageSettingsRead])
@inject
async def get_page_settings(
    current_user: User = Depends(get_current_user),
    page_settings_service: PageSettingsService = Depends(
        Provide[Container.page_settings_service]
    ),
):
    """Kullanicinin sayfa ayarlari.

    Ayarlara hic dokunulmamissa satir yok ve varsayilanlar donuyor;
    istemcinin "once bir kez olustur" adimi atmasi gerekmiyor.
    """
    ayarlar = await page_settings_service.get_settings(current_user.id)
    return SuccessResponse.create(
        data=ayarlar, message="Page settings retrieved successfully"
    )


@router.put("/page-settings", response_model=SuccessResponse[PageSettingsRead])
@inject
async def update_page_settings(
    settings_data: PageSettingsUpdate,
    current_user: User = Depends(get_current_user),
    page_settings_service: PageSettingsService = Depends(
        Provide[Container.page_settings_service]
    ),
):
    """Sayfa ayarlarini gunceller; satir yoksa ilk yazmada olusuyor.

    Arka plan, tema rengi ve profil fotografi BURADA DEGIL: onlar
    users tablosunda ve PUT /profile/update ile yonetiliyor. Ikisini de
    buradan kabul etmek ayni gorunumu iki ayri uctan degistirilebilir
    yapardi.
    """
    ayarlar = await page_settings_service.update_settings(
        current_user.id, settings_data
    )
    return SuccessResponse.create(
        data=ayarlar, message="Page settings updated successfully"
    )


@router.put("/update", response_model=SuccessResponse[UserRead])
@inject
async def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    """Update user profile (complete update)"""

    update_data = profile_data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(current_user, key, value)

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user, message="Profile updated successfully"
    )


@router.post("/skip-onboarding", response_model=SuccessResponse[UserRead])
@inject
async def skip_onboarding(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
):
    """Skip onboarding process"""

    current_user.onboarding_completed = True
    # profile_completed stays False

    updated_user = await user_service.update_user(current_user)

    return SuccessResponse.create(
        data=updated_user,
        message="Onboarding skipped. You can complete your profile later!",
    )


# Multipart zarfinin (sinir dizgileri, alan basliklari, dosya adi) payi.
# Govdenin geri kalani dosyanin kendisi.
_MULTIPART_PAYI = 64 * 1024


async def _eski_avatari_sil(depo: Depo, eski_adres: str | None, kullanici_id: int):
    """Eski avatar bu depodaki bu kullanicinin dosyasiysa siler.

    Silinemezse istek DUSMUYOR, yalnizca log: kullanicinin yeni avatari
    zaten kaydedildi; geride kalan sahipsiz bir dosya, basarili bir
    yuklemeyi hata gibi gostermekten daha az zararli.
    """
    anahtar = depo.anahtar_bul(eski_adres, kullanici_id)
    if not anahtar:
        return
    try:
        await depo.sil(anahtar)
    except Exception:
        logger.warning("Eski avatar silinemedi: %s", anahtar, exc_info=True)


@router.post("/avatar", response_model=SuccessResponse[UserRead])
@inject
async def upload_avatar(
    request: Request,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
    depo: Depo = Depends(Provide[Container.depo]),
):
    """Avatar yukler (multipart, alan adi `file`).

    Dosya oldugu gibi saklanmiyor: kare kirpilip JPEG/PNG olarak yeniden
    yaziliyor ve EXIF siliniyor (bkz. services/user/avatar.py). Eski avatar bu
    depodaysa siliniyor.

    NEDEN UploadFile PARAMETRESI DEGIL: FastAPI govdeyi ucun govdesine
    girmeden once ayristiriyor ve Starlette dosyalari BOYUT SINIRI
    OLMADAN diske yaziyor. Sinir ondan sonra kontrol edilseydi 2 GB'lik
    bir istek once diske inerdi. Burada Content-Length ayristirmadan
    ONCE kontrol ediliyor.
    """
    await say_ve_dogrula_hesap(str(current_user.id), "avatar", AVATAR_KULLANICI)

    sinir = settings.avatar_max_bytes
    try:
        uzunluk = int(request.headers["content-length"])
    except (KeyError, ValueError):
        # Uzunluksuz (chunked) govdede sinir onceden bilinemez.
        # Tarayicilar FormData gonderirken uzunlugu hep yaziyor.
        raise LengthRequiredException() from None
    if uzunluk > sinir + _MULTIPART_PAYI:
        raise PayloadTooLargeException(
            detail=f"Image must be at most {sinir // (1024 * 1024)} MB."
        )

    async with request.form(max_files=1, max_fields=0) as form:
        dosya = form.get("file")
        if not isinstance(dosya, UploadFile):
            raise ValidationException(detail="A file field named 'file' is required.")
        # Content-Length'e guvenilmiyor; okunan bayt da sinirli.
        ham = await dosya.read(sinir + 1)

    if len(ham) > sinir:
        raise PayloadTooLargeException(
            detail=f"Image must be at most {sinir // (1024 * 1024)} MB."
        )

    try:
        avatar = await run_in_threadpool(avatar_isle, ham)
    except GecersizGorsel as hata:
        raise ValidationException(detail=str(hata)) from None

    anahtar = avatar_anahtari(current_user.id, avatar.uzanti)
    adres = await depo.kaydet(anahtar, avatar.veri, avatar.icerik_turu)

    eski_adres = current_user.profile_image_url
    current_user.profile_image_url = adres
    try:
        guncel = await user_service.update_user(current_user)
    except Exception:
        # Kayit dustu: yazilan dosya hicbir kullaniciya bagli degil.
        # Silme de duserse ASIL hata (kayit) yukari gitmeli, onu
        # gizlememeli.
        try:
            await depo.sil(anahtar)
        except Exception:
            logger.warning("Sahipsiz avatar silinemedi: %s", anahtar, exc_info=True)
        raise

    await _eski_avatari_sil(depo, eski_adres, current_user.id)

    return SuccessResponse.create(data=guncel, message="Avatar uploaded successfully")


@router.delete("/avatar", response_model=SuccessResponse[UserRead])
@inject
async def delete_avatar(
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(Provide[Container.user_service]),
    depo: Depo = Depends(Provide[Container.depo]),
):
    """Avatari kaldirir; profil bas harflere doner.

    Eski serbest alandan kalma bir DIS adres de buradan kaldiriliyor
    (dosyasi bizde olmadigi icin yalnizca alan temizleniyor).
    """
    eski_adres = current_user.profile_image_url
    current_user.profile_image_url = None
    guncel = await user_service.update_user(current_user)

    await _eski_avatari_sil(depo, eski_adres, current_user.id)

    return SuccessResponse.create(data=guncel, message="Avatar removed")

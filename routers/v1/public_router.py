# routers/v1/public_router.py
"""Kimlik dogrulamasi gerektirmeyen public profil endpoint'leri."""

from typing import Annotated

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Path, Query

from core.schemas.response import SuccessResponse
from di.container import Container
from services.public.public_profile_dto import (
    PublicProfile,
    PublicProfileCount,
    PublicProfileRef,
)
from services.user.user_service import UserService

router = APIRouter(tags=["public"])

# Tek seferde donen en fazla satir. Sitemap standardi 50.000 URL'de
# kesiyor; buradaki sinir yanit boyutu icin, listenin tamami sayfalanarak
# aliniyor.
MAX_LIMIT = 5000


# DIKKAT - SIRA: bu route "/{username}"den ONCE tanimli olmali. Iki
# segmentli oldugu icin tek segmentli profil adresiyle zaten cakismiyor,
# ama tek segmentli yazilsaydi "sitemap" adli bir kullanicinin sayfasini
# golgelerdi. Ayri bir segment bu riski tamamen kaldiriyor.
@router.get(
    "/sitemap/profiles", response_model=SuccessResponse[list[PublicProfileRef]]
)
@inject
async def list_public_profiles(
    user_service: Annotated[UserService, Depends(Provide[Container.user_service])],
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 1000,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    """Sitemap icin profil adresleri ve son degisiklik tarihleri.

    Token gerektirmez; zaten herkese acik sayfalarin listesi. Yalnizca
    en az bir gorunur linki olan profiller doner -- bos bir sayfayi
    arama motoruna onermek ona da siteye de zarar veriyor.

    `limit`ten az satir donmesi listenin bittigini gosterir.
    """
    profiles = await user_service.list_public_profiles(limit=limit, offset=offset)
    return SuccessResponse.create(
        data=profiles,
        message="Public profiles retrieved successfully",
    )


@router.get(
    "/sitemap/count", response_model=SuccessResponse[PublicProfileCount]
)
@inject
async def count_public_profiles(
    user_service: Annotated[UserService, Depends(Provide[Container.user_service])],
):
    """Sitemap'e girecek profil sayisi.

    Frontend sitemap'i 50.000 URL'lik standart sinirin altinda tutmak
    icin parcalara boluyor ve kac parca gerektigini buradan ogreniyor.
    Listeyi bastan sona okuyup saymak, her parca icin butun listeyi
    cekmek demekti.

    Sayim, listeyle ayni kosulu kullaniyor (en az bir gorunur link);
    aksi halde parca sayisi liste uzunluguyla tutmazdi.
    """
    count = await user_service.count_public_profiles()
    return SuccessResponse.create(
        data=count,
        message="Public profile count retrieved successfully",
    )


@router.get("/{username}", response_model=SuccessResponse[PublicProfile])
@inject
async def get_public_profile(
    username: Annotated[
        str, Path(min_length=3, max_length=30, description="Profil kullanici adi")
    ],
    user_service: Annotated[UserService, Depends(Provide[Container.user_service])],
    count_view: Annotated[
        bool,
        Query(
            description=(
                "False verilirse bu cagri goruntulenme sayilmaz. "
                "Sayfanin kendisini degil, ayni profili yeniden okuyan "
                "yardimci istekleri (paylasim karti gibi) icindir."
            )
        ),
    ] = True,
):
    """Bir kullanicinin herkese acik link sayfasini doner.

    Token gerektirmez. Sadece aktif linkler ve gorunur profil alanlari doner;
    e-posta gibi hassas bilgiler bu yanitta yer almaz.

    NEDEN count_view: ayni ucu sayfa disinda cagiran yerler var --
    frontend paylasim kartini cizerken profili yeniden okuyor. Sayac
    varsayilan olarak arttigi icin bir kaziyicinin kart istegi
    "ziyaret" olarak sayiliyordu, yani kimsenin gormedigi bir sayfa
    goruntulenme uretiyordu. Bu bayrak o cagrilari sayimin disinda
    birakiyor.

    Kotuye kullanim tarafinda bir sey acmiyor: bayrak yalnizca sayimi
    *azaltabiliyor*, sisirmenin yolu degil -- sayac zaten istemcinin
    hic istek atmamasiyla da artmiyor.
    """
    profile = await user_service.get_public_profile(username, record_view=count_view)
    return SuccessResponse.create(
        data=profile,
        message="Public profile retrieved successfully",
    )

# routers/v1/link_router.py

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query, Request, status

from core.rate_limit import tekrar_mi
from core.schemas.response import SuccessResponse
from deps import get_current_user
from di.container import Container
from models import User
from services.link.link_service import LinkService
from services.link.link_service_dto import (
    LinkClickRequest,
    LinkCreate,
    LinkRead,
    LinkReorderRequest,
    LinkUpdate,
)
from settings import settings

router = APIRouter(tags=["links"])


@router.post(
    "/", response_model=SuccessResponse[LinkRead], status_code=status.HTTP_201_CREATED
)
@inject
async def create_link(
    link_data: LinkCreate,
    current_user: User = Depends(get_current_user),
    link_service: LinkService = Depends(Provide[Container.link_service]),
):
    """Yeni link oluşturur"""
    # NOT: Burada try/except yok. Onceki hali her hatayi yakalayip
    # ErrorResponse donuyordu, ama status_code 201 oldugu icin basarisiz
    # istekler de "201 Created" ile yanitlaniyordu. Hatalar artik global
    # exception handler'lara birakiliyor; dogru status kodu ve ayni hata
    # zarfi oradan geliyor (dosyadaki diger endpoint'lerle tutarli).
    link = await link_service.create_link(current_user.id, link_data)
    return SuccessResponse.create(data=link, message="Link successfully created")


@router.get("/", response_model=SuccessResponse[list[LinkRead]])
@inject
async def get_my_links(
    include_inactive: bool = Query(False, description="Include inactive links"),
    current_user: User = Depends(get_current_user),
    link_service: LinkService = Depends(Provide[Container.link_service]),
):
    """Kullanıcının linklerini getirir"""
    links = await link_service.get_user_links(current_user.id, include_inactive)
    return SuccessResponse.create(data=links, message="Links retrieved successfully")


@router.get("/{link_id}", response_model=SuccessResponse[LinkRead])
@inject
async def get_link(
    link_id: int,
    current_user: User = Depends(get_current_user),
    link_service: LinkService = Depends(Provide[Container.link_service]),
):
    """Belirli bir link getirir"""
    link = await link_service.get_link_by_id(link_id, current_user.id)
    return SuccessResponse.create(data=link, message="Link retrieved successfully")


@router.put("/{link_id}", response_model=SuccessResponse[LinkRead])
@inject
async def update_link(
    link_id: int,
    link_data: LinkUpdate,
    current_user: User = Depends(get_current_user),
    link_service: LinkService = Depends(Provide[Container.link_service]),
):
    """Link günceller"""
    link = await link_service.update_link(link_id, current_user.id, link_data)
    return SuccessResponse.create(data=link, message="Link successfully updated")


@router.delete("/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def delete_link(
    link_id: int,
    current_user: User = Depends(get_current_user),
    link_service: LinkService = Depends(Provide[Container.link_service]),
):
    """Link siler"""
    await link_service.delete_link(link_id, current_user.id)


@router.post("/reorder", response_model=SuccessResponse[list[LinkRead]])
@inject
async def reorder_links(
    reorder_data: LinkReorderRequest,
    current_user: User = Depends(get_current_user),
    link_service: LinkService = Depends(Provide[Container.link_service]),
):
    """Linklerin sırasını değiştirir"""
    links = await link_service.reorder_links(current_user.id, reorder_data)
    return SuccessResponse.create(data=links, message="Links reordered successfully")


@router.patch("/{link_id}/toggle", response_model=SuccessResponse[LinkRead])
@inject
async def toggle_link_status(
    link_id: int,
    current_user: User = Depends(get_current_user),
    link_service: LinkService = Depends(Provide[Container.link_service]),
):
    """Link'in aktif/pasif durumunu değiştirir"""
    link = await link_service.toggle_link_status(link_id, current_user.id)
    return SuccessResponse.create(data=link, message="Link status toggled successfully")


# NOT: GET /links/analytics/summary buradan kaldirildi. Tipsiz bir dict
# donuyordu ve profil goruntulenmesi gibi link disi metrikleri barindiramazdi.
# Yerine GET /analytics/summary geldi (routers/v1/analytics_router.py).


# Public endpoint - Link tıklandığında click count artırır
@router.post("/{link_id}/click", response_model=SuccessResponse[dict])
@inject
async def click_link(
    link_id: int,
    http_request: Request,
    payload: LinkClickRequest | None = None,
    link_service: LinkService = Depends(Provide[Container.link_service]),
):
    """Link tıklanma sayısını artırır ve redirect URL'sini döndürür.

    Govde opsiyonel; verilirse icindeki `referrer` ziyaretcinin bu sayfaya
    hangi siteden geldigini soyluyor. Istegin kendi Referer basligi bunun
    yerine gecemiyor: o her zaman bizim profil sayfamiz
    (bkz. services/link/link_service_dto.py).

    TEKILLESTIRME: ayni ziyaretcinin ayni linke kisa arayla yaptigi
    tekrar tiklamalar SAYILMIYOR (pencere: settings.click_dedup_seconds).
    Olculdu: tekillestirme yokken tek bir ziyaretcinin ~2 saniyede
    yaptigi 10 istek 10 tiklama olarak sayiliyordu.

    YANIT DEGISMIYOR. Tekrarlanan tiklama da 200 ve redirect_url aliyor;
    tekillestirilen sey SAYI. 429 ya da hata dondurmek, olcumu duzeltmek
    icin ziyaretcinin linke gitmesini engellemek olurdu.
    """
    tekrar = await tekrar_mi(http_request, link_id, settings.click_dedup_seconds)

    link = await link_service.increment_click_count(
        link_id,
        referrer=payload.referrer if payload else None,
        sayilsin=not tekrar,
    )
    return SuccessResponse.create(
        data={"redirect_url": link.url}, message="Click recorded successfully"
    )

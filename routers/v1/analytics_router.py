# routers/v1/analytics_router.py

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, Query

from core.schemas.response import SuccessResponse
from deps import get_current_user
from di.container import Container
from models import User
from services.analytics.analytics_dto import AnalyticsSummary, AnalyticsTimeseries
from services.analytics.analytics_service import MAX_DAYS, AnalyticsService

# Prefix disaridaki routers/analytics_router.py tarafindan veriliyor.
router = APIRouter(tags=["analytics"])


@router.get("/summary", response_model=SuccessResponse[AnalyticsSummary])
@inject
async def get_analytics_summary(
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(Provide[Container.analytics_service]),
):
    """Panonun ve analytics sayfasinin okudugu ozet.

    Onceki karsiligi GET /links/analytics/summary idi; hem tipsiz bir dict
    donuyordu hem de profil goruntulenmesi gibi link disi metrikler icin
    yanlis yerdeydi.
    """
    summary = await analytics_service.get_summary(current_user)
    return SuccessResponse.create(
        data=summary,
        message="Analytics retrieved successfully",
    )


@router.get("/timeseries", response_model=SuccessResponse[AnalyticsTimeseries])
@inject
async def get_analytics_timeseries(
    days: int = Query(
        7,
        ge=1,
        le=MAX_DAYS,
        description="Kac gunluk aralik dondurulecek (bugun dahil).",
    ),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(Provide[Container.analytics_service]),
):
    """Gunluk tiklama ve profil goruntulenme sayilari.

    Olay olmayan gunler de sifir degerlerle donuyor; grafigi cizen tarafin
    eksik gunleri tamamlamasi gerekmiyor.

    DIKKAT: Olay kaydi sonradan eklendi. Bu ucun toplamlari yalnizca olay
    tablosunun olusturuldugu tarihten sonrasini kapsar; /summary'deki
    toplamlar ise hesabin tum gecmisini sayar.
    """
    series = await analytics_service.get_timeseries(current_user, days)
    return SuccessResponse.create(
        data=series,
        message="Analytics timeseries retrieved successfully",
    )

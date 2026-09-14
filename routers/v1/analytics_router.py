# routers/v1/analytics_router.py

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends

from core.schemas.response import SuccessResponse
from deps import get_current_user
from di.container import Container
from models import User
from services.analytics.analytics_dto import AnalyticsSummary
from services.analytics.analytics_service import AnalyticsService

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

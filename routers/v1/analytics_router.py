# routers/v1/analytics_router.py

from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.schemas.response import SuccessResponse
from deps import get_current_user
from di.container import Container
from models import User
from services.analytics.analytics_dto import (
    AnalyticsSummary,
    AnalyticsTimeseries,
    BestTimes,
    LinkTimeseriesResponse,
    ReferrerBreakdown,
)
from services.analytics.analytics_service import (
    MAX_DAYS,
    AnalyticsService,
    Aralik,
    aralik_kur,
)

# Prefix disaridaki routers/analytics_router.py tarafindan veriliyor.
router = APIRouter(tags=["analytics"])


def aralik_baglayici(varsayilan_gun: int):
    """`days` ya da `start`/`end` okuyan bir bagimlilik uretir.

    NEDEN TEK YERDE: dort uc de ayni uc parametreyi aliyor ve ayni
    kurallari uyguluyor. Her ucta ayri ayri yazilsaydi, birinde atlanan
    bir kontrol yalnizca o ucu sessizce sinirsiz birakirdi.

    `days` geriye donuk uyumluluk icin duruyor ve varsayilan o; `start`
    ile `end` verilirse onlar geciyor.
    """

    def coz(
        days: int = Query(
            varsayilan_gun,
            ge=1,
            le=MAX_DAYS,
            description="Kac gunluk aralik dondurulecek (bugun dahil).",
        ),
        start: date | None = Query(
            None,
            description=(
                "Aralik baslangici (YYYY-AA-GG, UTC, dahil). end ile "
                "birlikte verilmeli; verilirse days yok sayilir."
            ),
        ),
        end: date | None = Query(
            None,
            description="Aralik sonu (YYYY-AA-GG, UTC, dahil).",
        ),
    ) -> Aralik:
        try:
            return aralik_kur(days=days, start=start, end=end)
        except ValueError as hata:
            # 422: istek bicimsel olarak dogru ama icerik gecersiz --
            # Query(ge=, le=) ne donduruyorsa aynisi.
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(hata),
            ) from hata

    return coz


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
    aralik: Aralik = Depends(aralik_baglayici(7)),
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
    series = await analytics_service.get_timeseries(current_user, aralik)
    return SuccessResponse.create(
        data=series,
        message="Analytics timeseries retrieved successfully",
    )


@router.get(
    "/timeseries/by-link", response_model=SuccessResponse[LinkTimeseriesResponse]
)
@inject
async def get_link_timeseries(
    aralik: Aralik = Depends(aralik_baglayici(7)),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(Provide[Container.analytics_service]),
):
    """Her linkin gunluk tiklama egrisi.

    Aralikta hic tiklanmayan linkler de sifir degerlerle listede: "bu link
    ise yaramadi" da bir bilgi.

    DIKKAT: Silinmis bir linke ait tiklamalar burada gorunmuyor (olay satiri
    duruyor ama artik bir linke baglanamiyor); /timeseries'te sayilmaya
    devam ediyorlar.
    """
    series = await analytics_service.get_link_timeseries(current_user, aralik)
    return SuccessResponse.create(
        data=series,
        message="Link timeseries retrieved successfully",
    )


@router.get("/referrers", response_model=SuccessResponse[ReferrerBreakdown])
@inject
async def get_referrers(
    aralik: Aralik = Depends(aralik_baglayici(7)),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(Provide[Container.analytics_service]),
):
    """Tiklamalarin hangi siteden geldigi.

    Kaynak, ziyaretcinin profil sayfasina gelmeden once bulundugu adresin
    host'u. Bunu frontend acikca gonderiyor: tiklama isteginin kendi Referer
    basligi her zaman bizim profil sayfamiz oldugu icin bu is icin
    kullanilamiyor (bkz. utils/referrer.py).

    DIKKAT: Referrer kolonu olay tablosundan sonra eklendi; daha eski
    tiklamalarin kaynagi bilinmedigi icin "dogrudan" sayiliyorlar.
    """
    breakdown = await analytics_service.get_referrers(current_user, aralik)
    return SuccessResponse.create(
        data=breakdown,
        message="Referrers retrieved successfully",
    )


@router.get("/best-times", response_model=SuccessResponse[BestTimes])
@inject
async def get_best_times(
    aralik: Aralik = Depends(aralik_baglayici(30)),
    tz: str = Query(
        "UTC",
        description=(
            "IANA saat dilimi, orn. 'Europe/Istanbul'. Saatler bu dilime "
            "gore gruplanir."
        ),
    ),
    current_user: User = Depends(get_current_user),
    analytics_service: AnalyticsService = Depends(Provide[Container.analytics_service]),
):
    """Tiklamalarin haftaguno ve saate dagilimi.

    Varsayilan aralik 7 degil 30 gun: haftanin her gununun birkac kez
    tekrarlanmadigi bir aralikta "hangi gun daha iyi" sorusu sorulamaz.

    Saat dilimi zorunlu degil ama neredeyse her zaman verilmeli. Olaylar
    UTC saklaniyor ve "en cok tiklama saat 14'te" bilgisi kullanicinin
    kendi saatine cevrilmeden bir sey anlatmiyor.

    DIKKAT: Yanittaki `enough_data` false iken `peak_weekday` /
    `peak_hour` bir cikarim degil, yalnizca en buyuk kutunun adi.
    """
    try:
        ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError) as hata:
        # 422: istek bicimsel olarak dogru ama icerik gecersiz -- days icin
        # Query(ge=, le=) ne donduruyorsa aynisi.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown timezone: {tz}",
        ) from hata

    best_times = await analytics_service.get_best_times(current_user, aralik, tz)
    return SuccessResponse.create(
        data=best_times,
        message="Best times retrieved successfully",
    )

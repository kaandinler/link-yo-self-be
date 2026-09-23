"""Uclarin kullandigi sinirlama yardimcilari."""

from fastapi import Request

from core.exceptions import RateLimitException
from core.rate_limit.keys import hesap_anahtari, ip_anahtari
from core.rate_limit.kurallar import Kural
from core.rate_limit.limiter import hiz_siniri
from settings import settings


def _kapali_mi() -> bool:
    return not settings.rate_limit_enabled


def _reddet(yeniden_dene: int) -> None:
    raise RateLimitException(
        detail="Too many requests. Please try again later.",
        retry_after=yeniden_dene,
    )


async def say_ve_dogrula(request: Request, kapsam: str, kural: Kural) -> None:
    """IP basina sayar; limit asilmissa 429.

    Her istegin kendi bedeli olan uclar icin (e-posta gonderen, hesap
    acan). Orada basarili/basarisiz ayrimi anlamsiz: istegin yapilmis
    olmasi zaten maliyet.
    """
    if _kapali_mi():
        return

    karar = await hiz_siniri.dene(
        ip_anahtari(request, kapsam), kural.limit, kural.pencere_sn
    )
    if not karar.izinli:
        _reddet(karar.yeniden_dene)


async def say_ve_dogrula_hesap(tanimlayici: str, kapsam: str, kural: Kural) -> None:
    """Hesap (e-posta / kullanici adi) basina sayar."""
    if _kapali_mi():
        return

    karar = await hiz_siniri.dene(
        hesap_anahtari(tanimlayici, kapsam), kural.limit, kural.pencere_sn
    )
    if not karar.izinli:
        _reddet(karar.yeniden_dene)


async def dogrula(
    request: Request,
    tanimlayici: str,
    kapsam: str,
    ip_kurali: Kural,
    hesap_kurali: Kural,
) -> None:
    """SAYMADAN bakar; iki katmandan biri doluysa 429.

    Giris icin. Sayma, ucun kendisinde ve YALNIZCA BASARISIZLIKTA
    yapiliyor (bkz. basarisizligi_isaretle): burada saysaydik dogru
    sifreyle giren kullanici da kendi limitini yakardi ve sik giris
    yapan biri kendini disari kilitleyebilirdi.
    """
    if _kapali_mi():
        return

    for anahtar, kural in (
        (ip_anahtari(request, kapsam), ip_kurali),
        (hesap_anahtari(tanimlayici, kapsam), hesap_kurali),
    ):
        karar = await hiz_siniri.bak(anahtar, kural.limit, kural.pencere_sn)
        if not karar.izinli:
            _reddet(karar.yeniden_dene)


async def basarisizligi_isaretle(
    request: Request,
    tanimlayici: str,
    kapsam: str,
    ip_kurali: Kural,
    hesap_kurali: Kural,
) -> None:
    """Basarisiz bir denemeyi iki katmana da yazar."""
    if _kapali_mi():
        return

    await hiz_siniri.isaretle(ip_anahtari(request, kapsam), ip_kurali.pencere_sn)
    await hiz_siniri.isaretle(
        hesap_anahtari(tanimlayici, kapsam), hesap_kurali.pencere_sn
    )


async def tekrar_mi(request: Request, link_id: int, pencere_sn: int) -> bool:
    """Bu tiklama ayni ziyaretciden gelen bir TEKRAR mi?

    True donerse sayilmamali. Ziyaretcinin linke gitmesi yine de
    engellenmiyor -- tekillestirilen sey SAYI, yanit degil.

    pencere_sn <= 0 ise tekillestirme kapali.

    Anahtar linke ozel: ayni ziyaretcinin iki FARKLI linke tiklamasi
    iki ayri tiklama, tek bir "bu kisi bugun tikladi" degil.
    """
    if pencere_sn <= 0:
        return False

    anahtar = ip_anahtari(request, f"tiklama:{link_id}")
    return not (await hiz_siniri.dene(anahtar, 1, pencere_sn)).izinli

"""Kayan pencereli istek sayaci.

NEDEN VAR: olculdu, hicbir uc sinirli degildi --
  - /v1/auth/token: 30 yanlis sifre, hepsi 401, tek bir 429 yok.
    Ardisik 3.1 deneme/sn; 40 es zamanli istek 11 saniyede tamamen
    servis edildi.
  - /v1/auth/forgot-password: 20 istek -> 20 e-posta, ayni adrese.
  - /v1/auth/register: 15 deneme -> 15 hesap.

NEDEN KAYAN PENCERE (sabit pencere degil): sabit pencerede saldirgan
pencerenin son saniyesinde limiti doldurup yeni pencerenin ilk
saniyesinde tekrar doldurabilir -- yani kisa bir anda iki kat istek
geciriebilir. Kayan pencere bu kaciri kapatiyor ve bedeli, anahtar
basina en fazla `limit` kadar zaman damgasi tutmak.

NEDEN SUREC ICI BELLEK (Redis degil): bu yiginda Redis yok ve yalnizca
bunun icin bir bagimlilik eklemek, isletilecek ikinci bir servis
demekti. BEDELI ACIKCA SOYLENMELI: sinirlar SUREC BASINA gecerli.
Uygulama N isci ile kosarsa gercek sinir N katina cikar ve surec
yeniden baslayinca sayaclar sifirlanir. Bu, sinirsiz olmaktan cok daha
iyi ama Redis'li bir cozumle ayni sey degil; kalici bir sinir
gerektiginde bu modulun yerine paylasilan bir depo konmali.
"""

import time
from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Karar:
    izinli: bool
    """Pencerede kalan hak (izinli=False iken 0)."""
    kalan: int
    """Kac saniye sonra yeniden denenebilir (izinli=True iken 0)."""
    yeniden_dene: int


class HizSiniri:
    """Anahtar basina kayan pencere.

    Tek olay dongusunde calisiyor: iki istegin arasina await girmedigi
    icin ayrica kilit gerekmiyor.
    """

    def __init__(self, anahtar_tavani: int = 50_000):
        # Bellek saldirgan tarafindan buyutulemesin: her IP yeni bir
        # anahtar demek ve IP dondurmek ucuz. Tavana gelince once
        # suresi gecenler, sonra en eskiler atiliyor.
        self._anahtar_tavani = anahtar_tavani
        self._damgalar: dict[str, deque[float]] = {}

    def bak(self, anahtar: str, limit: int, pencere_sn: int) -> Karar:
        """Sayaci ARTIRMADAN durumu soyler."""
        kuyruk = self._temizlenmis_kuyruk(anahtar, pencere_sn)
        simdi = time.monotonic()

        if len(kuyruk) >= limit:
            # En eski damga pencereden cikinca bir hak aciliyor.
            bekleme = kuyruk[0] + pencere_sn - simdi
            return Karar(izinli=False, kalan=0, yeniden_dene=max(1, int(bekleme) + 1))

        return Karar(izinli=True, kalan=limit - len(kuyruk), yeniden_dene=0)

    def isaretle(self, anahtar: str, pencere_sn: int) -> None:
        """Bir olayi sayar.

        NEDEN `bak`TAN AYRI: girişte yalnizca BASARISIZ denemeler
        sayiliyor. Tek bir `dene` olsaydi dogru sifreyle giren
        kullanici da kendi limitini yakardi ve sik giris yapan biri
        kendini disari kilitleyebilirdi. Ucun once bakmasi, sonra
        sonuca gore isaretlemesi bunu ayiriyor.
        """
        self._temizlenmis_kuyruk(anahtar, pencere_sn).append(time.monotonic())

    def dene(self, anahtar: str, limit: int, pencere_sn: int) -> Karar:
        """Bak + izinliyse isaretle.

        Her istegin kendi bedeli olan uclar icin (bir e-posta gonderen,
        bir hesap acan). Orada "basarili/basarisiz" ayrimi yok: istegin
        yapilmis olmasi zaten maliyet.
        """
        karar = self.bak(anahtar, limit, pencere_sn)
        if karar.izinli:
            self.isaretle(anahtar, pencere_sn)
        return karar

    def _temizlenmis_kuyruk(self, anahtar: str, pencere_sn: int) -> deque[float]:
        simdi = time.monotonic()
        sinir = simdi - pencere_sn

        kuyruk = self._damgalar.get(anahtar)
        if kuyruk is None:
            self._yer_ac()
            kuyruk = deque()
            self._damgalar[anahtar] = kuyruk

        while kuyruk and kuyruk[0] <= sinir:
            kuyruk.popleft()

        return kuyruk

    def sifirla(self) -> None:
        """Butun sayaclari siler. Testler icin."""
        self._damgalar.clear()

    def _yer_ac(self) -> None:
        if len(self._damgalar) < self._anahtar_tavani:
            return

        # Bos kalmis (butun damgalari eskimis) anahtarlari at.
        for anahtar in [a for a, k in self._damgalar.items() if not k]:
            del self._damgalar[anahtar]

        # Hala doluysa en eski dokunulan anahtari at. dict ekleme
        # sirasini korudugu icin ilk anahtar en eskisi.
        while len(self._damgalar) >= self._anahtar_tavani:
            en_eski = next(iter(self._damgalar))
            del self._damgalar[en_eski]


# Uygulama boyunca tek ornek.
hiz_siniri = HizSiniri()

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

IKI DEPO:

  REDIS_URL verilmemis -> surec ici bellek (varsayilan). Ikinci bir
  servis gerektirmiyor. BEDELI: sinirlar SUREC BASINA. Olculdu, hesap
  basina 10 yanlis sifre kuralinda, 60 denemeden sifre kontrolune
  ulasan (429'lar yok sayilarak, gercek bir saldirgan gibi):

      1 isci -> 10     2 isci -> 20     4 isci -> 31-33

  REDIS_URL verilmis -> Redis. Butun isciler ve sunucular AYNI sayaci
  goruyor; ayni olcum isci sayisindan bagimsiz olarak 10.

Redis ulasilamazsa bellek deposuna dusuluyor (bkz. HizSiniri): kesinti
sirasinda sinirlar yine surec basina ama SIFIR degil. Iki kotu secenek
vardi -- butun istekleri kabul etmek (kaba kuvvete kapi acar) ya da
butun istekleri reddetmek (Redis dustu diye kimse giris yapamaz) --
ikisi de bundan kotu.
"""

import logging
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Karar:
    izinli: bool
    """Pencerede kalan hak (izinli=False iken 0)."""
    kalan: int
    """Kac saniye sonra yeniden denenebilir (izinli=True iken 0)."""
    yeniden_dene: int


class BellekDeposu:
    """Surec ici bellekte, anahtar basina kayan pencere.

    Tek olay dongusunde calisiyor: iki istegin arasina await girmedigi
    icin ayrica kilit gerekmiyor.
    """

    # Tavan doluyken suresi dolmus anahtar taramasi en fazla bu siklikta.
    # Tarama O(n); her yeni anahtarda yapilsaydi, tavani dolduran bir
    # saldiri her istekte 50.000 anahtari gezdirirdi.
    _TARAMA_ARALIGI_SN = 1.0

    def __init__(self, anahtar_tavani: int = 50_000):
        # Bellek saldirgan tarafindan buyutulemesin: her IP yeni bir
        # anahtar demek ve IP dondurmek ucuz. Tavana gelince once
        # suresi gecenler, sonra en uzun suredir dokunulmayanlar atiliyor.
        self._anahtar_tavani = anahtar_tavani
        # Sira = dokunma sirasi (bkz. _temizlenmis_kuyruk, move_to_end).
        self._damgalar: OrderedDict[str, deque[float]] = OrderedDict()
        # Anahtarin son olayinin pencereden cikacagi an. Kuyruk ancak
        # anahtara dokunulunca temizleniyor; suresi dolmus bir anahtari
        # tanimak icin kuyruga degil buna bakmak gerekiyor.
        self._bitis: dict[str, float] = {}
        self._son_tarama = float("-inf")

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
        simdi = time.monotonic()
        self._temizlenmis_kuyruk(anahtar, pencere_sn).append(simdi)
        self._bitis[anahtar] = simdi + pencere_sn

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
        else:
            # Dokunuldu: tahliye sirasinda en sona.
            self._damgalar.move_to_end(anahtar)

        while kuyruk and kuyruk[0] <= sinir:
            kuyruk.popleft()

        return kuyruk

    def sifirla(self) -> None:
        """Butun sayaclari siler. Testler icin."""
        self._damgalar.clear()
        self._bitis.clear()
        self._son_tarama = float("-inf")

    def _yer_ac(self) -> None:
        """Tavan doluysa yer acar: once suresi dolmuslar, sonra en uzun
        suredir dokunulmayanlar.

        ONCEKI HALI BU IKISINI DE YAPMIYORDU, aciklamasi oyle dese de:
          - Yalnizca kuyrugu BOS anahtarlari siliyordu. Kuyruk ancak
            anahtara dokunulunca temizleniyor; suresi dolmus ama bir
            daha dokunulmamis anahtarin kuyrugu dolu duruyor ve
            "suresi dolmus" sayilmiyordu.
          - "En eski dokunulan" diye dict'in ILK anahtarini atiyordu, ama
            dokunmak sirayi degistirmiyordu; yani en eski EKLENEN.
        Olculdu: tavan 3; once canli bir anahtar (1 hak, 1 saat, hakki
        bitmis), sonra suresi dolmus iki anahtar, sonra yeni bir anahtar.
        Silinen suresi dolmuslardan biri degil CANLI anahtardi ve hakki
        SIFIRLANDI -- bir sonraki denemesi yeniden izinli dondu.

        Bir tavan, dolduran bir saldiriya karsi her canli sayaci
        koruyamaz; bu, surec ici belleginin sinirida ve Redis deposunun
        var olma sebebi. Ama dogal olarak suresi dolan anahtarlar
        varken canli bir sayaci atmak gereksizdi.
        """
        if len(self._damgalar) < self._anahtar_tavani:
            return

        simdi = time.monotonic()
        if simdi - self._son_tarama >= self._TARAMA_ARALIGI_SN:
            self._son_tarama = simdi
            # Hic isaretlenmemis (yalnizca bak edilmis) anahtarin bitisi
            # yok: tutacak bir sey yok, o da gidiyor.
            for anahtar in [
                a for a in self._damgalar if self._bitis.get(a, float("-inf")) <= simdi
            ]:
                del self._damgalar[anahtar]
                self._bitis.pop(anahtar, None)

        while len(self._damgalar) >= self._anahtar_tavani:
            anahtar, _ = self._damgalar.popitem(last=False)
            self._bitis.pop(anahtar, None)


# --- Redis ----------------------------------------------------------------

# Kontrol ve (istenirse) isaretleme TEK betikte, yani atomik. Ayri
# komutlarla yapilsaydi iki isci ayni anda "9 < 10" gorup ikisi de
# isaretler ve sinir 11 olurdu -- tam da duzeltilen sorunun kucugu.
#
# Saat Redis'in saati (TIME): isciler/sunucular arasindaki saat farki
# pencereyi kaydirmasin. Bellek deposunun time.monotonic()'i surec ici
# oldugu icin zaten paylasilamazdi.
#
# Uye adi benzersiz (zaman damgasi degil): ayni milisaniyedeki iki olay
# ayni uyeyi yazip tek sayilmasin.
_KONTROL = """
local t = redis.call('TIME')
local simdi = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local pencere = tonumber(ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', simdi - pencere)
local sayi = redis.call('ZCARD', KEYS[1])
local limit = tonumber(ARGV[1])
if sayi >= limit then
  local en_eski = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return {0, 0, tonumber(en_eski[2]) + pencere - simdi}
end
if ARGV[3] == '1' then
  redis.call('ZADD', KEYS[1], simdi, ARGV[4])
  redis.call('PEXPIRE', KEYS[1], pencere)
end
return {1, limit - sayi, 0}
"""

_ISARETLE = """
local t = redis.call('TIME')
local simdi = tonumber(t[1]) * 1000 + math.floor(tonumber(t[2]) / 1000)
local pencere = tonumber(ARGV[1])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', simdi - pencere)
redis.call('ZADD', KEYS[1], simdi, ARGV[2])
redis.call('PEXPIRE', KEYS[1], pencere)
return 1
"""

_ONEK = "hs:"


class RedisDeposu:
    """Butun surecler arasinda paylasilan kayan pencere.

    Anahtar basina bir sorted set: uyeler olaylar, skorlar zamanlari.
    PEXPIRE sayesinde bos kalan anahtar kendiliginden siliniyor -- bellek
    deposundaki anahtar tavanina burada gerek yok.
    """

    def __init__(self, istemci):
        self._istemci = istemci
        self._kontrol = istemci.register_script(_KONTROL)
        self._isaretle = istemci.register_script(_ISARETLE)

    async def _calistir(
        self, anahtar: str, limit: int, pencere_sn: int, isaretle: bool
    ) -> Karar:
        izinli, kalan, bekleme_ms = await self._kontrol(
            keys=[_ONEK + anahtar],
            args=[limit, pencere_sn * 1000, "1" if isaretle else "0", uuid.uuid4().hex],
        )
        if not izinli:
            return Karar(
                izinli=False, kalan=0, yeniden_dene=max(1, int(bekleme_ms) // 1000 + 1)
            )
        return Karar(izinli=True, kalan=int(kalan), yeniden_dene=0)

    async def bak(self, anahtar: str, limit: int, pencere_sn: int) -> Karar:
        return await self._calistir(anahtar, limit, pencere_sn, isaretle=False)

    async def dene(self, anahtar: str, limit: int, pencere_sn: int) -> Karar:
        return await self._calistir(anahtar, limit, pencere_sn, isaretle=True)

    async def isaretle(self, anahtar: str, pencere_sn: int) -> None:
        await self._isaretle(
            keys=[_ONEK + anahtar], args=[pencere_sn * 1000, uuid.uuid4().hex]
        )

    async def sifirla(self) -> None:
        async for anahtar in self._istemci.scan_iter(match=_ONEK + "*"):
            await self._istemci.delete(anahtar)

    async def kapat(self) -> None:
        await self._istemci.aclose()


# --- Cephe ----------------------------------------------------------------


class HizSiniri:
    """Uclarin kullandigi arayuz. Redis varsa Redis, yoksa bellek.

    ASYNC, cunku Redis ag istegi. Senkron bir Redis istemcisi olay
    dongusunu durdururdu -- e-posta gondericisinde olculup duzeltilen
    kusurun aynisi (bkz. core/email/sender.py).

    Redis hatasinda bellek deposuna dusuluyor ve bir UYARI yaziliyor;
    uyari dakikada bir kezle sinirli, yoksa kesinti boyunca her istek
    bir log satiri uretirdi.
    """

    _UYARI_ARALIGI_SN = 60

    def __init__(self, redis_url: str | None = None, anahtar_tavani: int = 50_000):
        self._bellek = BellekDeposu(anahtar_tavani=anahtar_tavani)
        self._redis: RedisDeposu | None = None
        self._son_uyari = float("-inf")
        if redis_url:
            import redis.asyncio as redis_async

            # Baglanti ilk komutta kuruluyor; ayaga kalkarken Redis'in
            # hazir olmasi gerekmiyor. Zaman asimi kisa: sinirlayici bir
            # girisi beklettigi her saniye, kullanicinin bekledigi saniye.
            self._redis = RedisDeposu(
                redis_async.from_url(
                    redis_url, socket_timeout=0.5, socket_connect_timeout=0.5
                )
            )

    def _redis_dustu(self, hata: Exception) -> None:
        simdi = time.monotonic()
        if simdi - self._son_uyari >= self._UYARI_ARALIGI_SN:
            self._son_uyari = simdi
            logger.warning(
                "Hiz siniri Redis'e ulasamadi, surec ici belleğe dusuldu: %s", hata
            )

    async def bak(self, anahtar: str, limit: int, pencere_sn: int) -> Karar:
        if self._redis:
            try:
                return await self._redis.bak(anahtar, limit, pencere_sn)
            except Exception as hata:  # noqa: BLE001 - bilincli geri dusus
                self._redis_dustu(hata)
        return self._bellek.bak(anahtar, limit, pencere_sn)

    async def dene(self, anahtar: str, limit: int, pencere_sn: int) -> Karar:
        if self._redis:
            try:
                return await self._redis.dene(anahtar, limit, pencere_sn)
            except Exception as hata:  # noqa: BLE001 - bilincli geri dusus
                self._redis_dustu(hata)
        return self._bellek.dene(anahtar, limit, pencere_sn)

    async def isaretle(self, anahtar: str, pencere_sn: int) -> None:
        if self._redis:
            try:
                await self._redis.isaretle(anahtar, pencere_sn)
                return
            except Exception as hata:  # noqa: BLE001 - bilincli geri dusus
                self._redis_dustu(hata)
        self._bellek.isaretle(anahtar, pencere_sn)

    async def sifirla(self) -> None:
        """Butun sayaclari siler. Testler icin."""
        self._bellek.sifirla()
        if self._redis:
            await self._redis.sifirla()

    async def kapat(self) -> None:
        """Redis baglanti havuzunu kapatir. Testler icin: her testin olay
        dongusu ayri ve havuz olustugu donguye bagli."""
        if self._redis:
            await self._redis.kapat()


def _olustur() -> HizSiniri:
    # settings burada, modul seviyesinde degil: kurallar.py uzerinden
    # dairesel import riski (bkz. settings.click_dedup_seconds notu).
    from settings import settings

    return HizSiniri(settings.redis_url)


# Uygulama boyunca tek ornek.
hiz_siniri = _olustur()

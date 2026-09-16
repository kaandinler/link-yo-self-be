"""Ziyaretcinin geldigi adresi gosterilebilir bir "kaynak"a cevirir.

NEDEN BU MODUL VAR: Tiklama ucuna gelen Referer *basligi* bu is icin
kullanilamaz. Tiklama kaydi, ziyaretcinin zaten bizim profil sayfamizdayken
yaptigi bir XHR; tarayicinin o istege koydugu Referer her zaman kendi
sayfamiz. "Trafik nereden geliyor" sorusunu cevaplayan deger, profil
sayfasindaki document.referrer -- yani ziyaretci bize gelmeden once nerede
oldugu. Bunu yalnizca frontend biliyor ve acikca gonderiyor
(bkz. LinkClickRequest.referrer).
"""

import re
from collections.abc import Collection
from urllib.parse import urlsplit

from settings import settings

# analytics_events.referrer kolonunun genisligi.
MAX_HOST_LENGTH = 255

# Gosterilebilir bir host: harf/rakamla baslayip biten, arada nokta, tire ve
# alt tire. Ayrastirilamayan girdiler ("hello world", IPv6 adresleri) bilerek
# eleniyor: panoda anlamsiz bir satir gostermektense "Direct" saymak dogru.
_HOST_DESENI = re.compile(r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$")


def host_ayikla(adres: str | None) -> str | None:
    """Tam bir URL'den gosterilebilir host'u cikarir.

    "https://www.instagram.com/p/abc?utm_source=x" -> "instagram.com"

    "www." atiliyor: www.google.com ile google.com ayni kaynak, panoda iki
    satir olmalari yalnizca gurultu.

    Ayrastirilamayan ya da host icermeyen her girdi icin None doner.
    """
    if not adres:
        return None

    adres = adres.strip()
    if not adres:
        return None

    parcalar = urlsplit(adres)
    host = parcalar.hostname
    if not host and not parcalar.scheme:
        # Semasiz gonderilmis olabilir ("instagram.com/p/abc"); urlsplit bunu
        # yol sayiyor. Tarayici document.referrer'i her zaman semayla verir,
        # bu dal API'yi elle cagiranlar icin. Sema varken denenmiyor: aksi
        # halde "javascript:void(0)" host'u "javascript" olurdu.
        host = urlsplit(f"//{adres}").hostname

    if not host:
        return None

    host = host.lower().removeprefix("www.")

    # Kolona sigmayan bir host gercek bir alan adi degil (DNS siniri 253):
    # kirpmak uydurma bir kaynak yaratirdi, bu yuzden eleniyor.
    if len(host) > MAX_HOST_LENGTH or not _HOST_DESENI.match(host):
        return None

    return host


def kendi_hostlarimiz() -> set[str]:
    """Uygulamanin kendi frontend host'lari.

    frontend_url her ortamda dolu; allowed_origins production'da birden fazla
    alan adi olabilecegi icin ek olarak taraniyor.
    """
    adresler = [settings.frontend_url, *(settings.allowed_origins or [])]
    return {host for host in map(host_ayikla, adresler) if host}


def kaynak_host(
    referrer: str | None, ic_hostlar: Collection[str] | None = None
) -> str | None:
    """Referrer'i kaydedilecek kaynak host'a cevirir; yoksa None.

    None donmesi "dogrudan" demek: adres cubuguna yazilmis, referrer'i
    gizleyen bir uygulamadan gelinmis ya da site ici gezinme olmus.

    Site ici gezinme neden dogrudan sayiliyor: kullanici kendi ana
    sayfamizdan profil sayfasina gectiyse bu bir *trafik kaynagi* degil;
    listede kendi alan adimizi en ust sirada gormek paneli yaniltirdi.
    """
    host = host_ayikla(referrer)
    if host is None:
        return None

    if ic_hostlar is None:
        ic_hostlar = kendi_hostlarimiz()

    if host in ic_hostlar:
        return None

    return host

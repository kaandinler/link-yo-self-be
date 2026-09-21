"""Sinirlamanin anahtarlari.

IKI KATMAN VAR VE IKISI DE GEREKLI:

  - IP: dagitik olmayan denemeyi ve kayit spam'ini durduruyor. Kayitta
    henuz bir hesap yok, yani IP disinda sinirlanacak bir sey de yok.
  - Hesap (e-posta/kullanici adi): tek bir hesaba yonelen denemeyi ve
    tek bir adrese e-posta bombardimanini, saldirgan IP degistirse bile
    durduruyor.

Biri digerinin yerini tutmuyor; ayri ayri sayiliyorlar.
"""

import hashlib

from fastapi import Request

from settings import settings

BILINMEYEN = "bilinmeyen"


def _ham_ip(request: Request) -> str:
    """Istemcinin IP'si.

    X-FORWARDED-FOR KORU KORUNE OKUNMUYOR. Basligi istemci uydurabilir;
    her istekte rastgele bir deger yazan biri, ona guvenen bir
    sinirlayiciyi tamamen atlatir -- yani sinir tiyatroya doner.

    Kural: `trusted_proxy_count` kac tane GUVENILIR ters vekil
    oldugunu soyluyor.
      - 0 (varsayilan): baslik hic okunmuyor, baglantinin kendi adresi
        kullaniliyor. Vekil arkasinda degilken dogrusu bu.
      - N > 0: X-Forwarded-For'un SAGDAN N. elemani aliniyor. Vekiller
        gordukleri adresi saga ekliyor, yani sagdaki N eleman bizim
        altyapimiza ait; saldirganin yazabildigi kisim solda kaliyor.
    """
    vekil_sayisi = settings.trusted_proxy_count

    if vekil_sayisi > 0:
        baslik = request.headers.get("x-forwarded-for")
        if baslik:
            adresler = [parca.strip() for parca in baslik.split(",") if parca.strip()]
            if len(adresler) >= vekil_sayisi:
                return adresler[-vekil_sayisi]

    if request.client and request.client.host:
        return request.client.host

    return BILINMEYEN


def ip_anahtari(request: Request, kapsam: str) -> str:
    """IP'nin OZETI -- ham adres hicbir yerde tutulmuyor.

    NEDEN OZET: sayaclar bellekte, ama bir bellek dokumu ya da hata
    ayiklama ciktisi yine de ham adresleri gosterebilirdi. Ozet, ayni
    isi goruyor (ayni IP ayni anahtari uretiyor) ve adresi geri
    vermiyor. Kalicilik zaten yok: pencere dolunca kayit siliniyor.
    """
    ozet = hashlib.sha256(_ham_ip(request).encode()).hexdigest()[:32]
    return f"{kapsam}:ip:{ozet}"


def hesap_anahtari(tanimlayici: str, kapsam: str) -> str:
    """E-posta ya da kullanici adi; ozetlenerek.

    Kucuk harfe indiriliyor: "Kaan@x.com" ile "kaan@x.com" ayni hesap,
    ayri anahtar olmalari sinirin etrafindan dolasmayi kolaylastirirdi.
    """
    ozet = hashlib.sha256(tanimlayici.strip().lower().encode()).hexdigest()[:32]
    return f"{kapsam}:hesap:{ozet}"

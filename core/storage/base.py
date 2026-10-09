"""Depo arayuzu ve anahtar kurallari."""

import re
import uuid
from abc import ABC, abstractmethod

# Anahtarin BUTUN sekli. Silme yalnizca bu kalibi tasiyan anahtarlara
# yapiliyor; bkz. Depo.anahtar_bul.
_AVATAR_ANAHTARI = re.compile(r"^avatars/(\d+)/[0-9a-f]{32}\.(jpg|png)$")


def avatar_anahtari(kullanici_id: int, uzanti: str) -> str:
    """Yeni bir avatar icin anahtar.

    NEDEN HER YUKLEMEDE YENI AD: ayni adin uzerine yazilsaydi tarayicilar
    ve CDN eski gorseli onbellekten gostermeye devam ederdi. Ad degisince
    dosya degismez (immutable) sayilabiliyor ve uzun sure onbelleklenebiliyor.
    """
    return f"avatars/{kullanici_id}/{uuid.uuid4().hex}.{uzanti}"


def avatar_anahtari_mi(anahtar: str, kullanici_id: int) -> bool:
    """Anahtar bu kullanicinin bir avatari mi?

    KULLANICI KONTROLU NEDEN VAR: profile_image_url eskiden serbest bir
    alandi; biri kendi alanina BASKASININ avatar adresini yazmis olabilir.
    Kontrol olmasaydi o kisi yeni avatar yuklediginde "eski avatarini"
    silerken baskasinin dosyasini silerdik.
    """
    eslesme = _AVATAR_ANAHTARI.match(anahtar)
    return bool(eslesme) and int(eslesme.group(1)) == kullanici_id


class Depo(ABC):
    """Dosya deposu.

    Adresler MUTLAK: profile_image_url'e yaziliyor ve tarayici dogrudan
    onu yukluyor.
    """

    #: Dosyalarin disaridan gorunen kok adresi, sonda "/" olmadan.
    kok_adres: str

    @abstractmethod
    async def kaydet(self, anahtar: str, veri: bytes, icerik_turu: str) -> str:
        """Dosyayi yazar, herkese acik adresini doner."""

    @abstractmethod
    async def sil(self, anahtar: str) -> None:
        """Dosyayi siler; yoksa hata vermez."""

    def adres(self, anahtar: str) -> str:
        return f"{self.kok_adres}/{anahtar}"

    def anahtar_bul(self, adres: str | None, kullanici_id: int) -> str | None:
        """Adres bu depoda bu kullaniciya ait bir avatarsa anahtari.

        Degilse None: dis bir adres (eski serbest alan), baska bir
        deponun adresi ya da baskasinin dosyasi. None donen adres icin
        hicbir sey silinmiyor.
        """
        if not adres or not adres.startswith(f"{self.kok_adres}/"):
            return None
        anahtar = adres[len(self.kok_adres) + 1 :]
        return anahtar if avatar_anahtari_mi(anahtar, kullanici_id) else None

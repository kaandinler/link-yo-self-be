"""Sosyal hesap uclarinin istek/yanit semalari.

URL dogrulamasi link DTO'sundakiyle ayni kurallari izliyor: sema yoksa
https:// ekleniyor ve basit bir bicim kontrolunden geciyor. Iki yerde
ayni regex duruyor cunku ortak bir yardimciya cikarmak link DTO'sunu da
degistirmeyi gerektirirdi; bu PR'in isi o degil.
"""

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Link DTO'sundakiyle ayni desen.
URL_DESENI = re.compile(
    r'^https?://'
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
    r'localhost|'
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
    r'(?::\d+)?'
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)


def _url_dogrula(url: str) -> str:
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    if not URL_DESENI.match(url):
        raise ValueError("Invalid URL format")

    return url


class SocialAccountCreate(BaseModel):
    """Yeni sosyal hesap.

    NEDEN profile_url ZORUNLU: platform tablosunda adres sablonu tutan bir
    kolon yok (yalnizca name + display_name). Adresi platform adiyla
    kullanici adindan turetmek her platform icin ayri bir tahmin demek
    olurdu; istemci tam adresi gonderiyor.
    """

    platform_id: int = Field(..., ge=1, description="Platform ID")
    username: str = Field(..., min_length=1, max_length=100)
    profile_url: str = Field(..., min_length=1, max_length=2048)

    @field_validator("username", mode="before")
    @classmethod
    def kullanici_adini_kirp(cls, username: str) -> str:
        # Bastaki/sondaki bosluk kirpiliyor: aksi halde "kaan" ve "kaan "
        # tekillik kisitina gore iki ayri kayit olurdu.
        return username.strip() if isinstance(username, str) else username

    @field_validator("profile_url", mode="before")
    @classmethod
    def adresi_dogrula(cls, url: str) -> str:
        return _url_dogrula(url)


class SocialAccountUpdate(BaseModel):
    """Kismi guncelleme; verilmeyen alan degismiyor."""

    platform_id: int | None = Field(None, ge=1)
    username: str | None = Field(None, min_length=1, max_length=100)
    profile_url: str | None = Field(None, min_length=1, max_length=2048)

    @field_validator("username", mode="before")
    @classmethod
    def kullanici_adini_kirp(cls, username: str | None) -> str | None:
        if username is None:
            return username
        return username.strip() if isinstance(username, str) else username

    @field_validator("profile_url", mode="before")
    @classmethod
    def adresi_dogrula(cls, url: str | None) -> str | None:
        if url is None:
            return url
        return _url_dogrula(url)


class PlatformRead(BaseModel):
    id: int
    name: str
    display_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class SocialAccountRead(BaseModel):
    id: int
    user_id: int
    platform_id: int
    username: str
    profile_url: str

    model_config = ConfigDict(from_attributes=True)

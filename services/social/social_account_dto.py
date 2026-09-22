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
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


def _url_dogrula(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

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


# --- Platform yonetimi (admin) -------------------------------------------

# Platform adi bir SLUG: kucuk harf, rakam, tire ve nokta. Seed'deki 20
# kayit da bu bicimde ("x", "tiktok", "linkedin"). Gosterim adi ayri bir
# kolon oldugu icin buranin okunabilir olmasi gerekmiyor; tekilligin ve
# istikrarin tasiyicisi bu.
PLATFORM_ADI_DESENI = re.compile(r"^[a-z0-9][a-z0-9.\-]*$")


def _platform_adi_dogrula(name: str) -> str:
    ad = name.strip().lower()
    if not PLATFORM_ADI_DESENI.match(ad):
        raise ValueError(
            "Platform name must be lowercase letters, digits, dots or hyphens"
        )
    return ad


class PlatformAdminRead(BaseModel):
    """Yonetim ekraninin gordugu platform.

    PlatformRead'den iki alan fazla ve ikisi de karar icin:
      - `is_retired`: emekliye ayrilmis mi (kullaniciya gosterilen
        listede bu kayitlar hic gorunmuyor).
      - `account_count`: kac kullanici bu platformu kullaniyor.
        Yonetici, emekliye ayirmanin kimi etkileyecegini gormeden
        karar vermemeli.
    """

    id: int
    name: str
    display_name: str | None = None
    is_retired: bool
    account_count: int


class PlatformCreate(BaseModel):
    """Yeni platform.

    NEDEN AD KUCUK HARFE CEVRILIYOR: kolon UNIQUE ve "TikTok" ile
    "tiktok" veritabani icin iki ayri kayit. Ikisi birden var olsaydi
    secim listesinde ayni platform iki kez gorunurdu.
    """

    name: str = Field(..., min_length=1, max_length=50)
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def adi_dogrula(cls, name: str) -> str:
        return _platform_adi_dogrula(name) if isinstance(name, str) else name

    @field_validator("display_name", mode="before")
    @classmethod
    def gosterim_adini_kirp(cls, deger: str | None) -> str | None:
        if not isinstance(deger, str):
            return deger
        kirpilmis = deger.strip()
        return kirpilmis or None


class PlatformUpdate(BaseModel):
    """Platform guncelleme.

    AD DEGISTIRILEMIYOR ve bu bilincli: ad, sosyal hesaplarin bagli
    oldugu kimligin okunabilir tarafi ve herkese acik profilde ikon
    secimine kadar her yerde kullaniliyor. Degistirmek isteyen yeni bir
    platform acip eskisini emekliye ayirabilir. Gosterim adi serbest.
    """

    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("display_name", mode="before")
    @classmethod
    def gosterim_adini_kirp(cls, deger: str | None) -> str | None:
        if not isinstance(deger, str):
            return deger
        kirpilmis = deger.strip()
        return kirpilmis or None

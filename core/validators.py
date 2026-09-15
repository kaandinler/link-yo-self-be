"""Profil alanlari icin ortak dogrulama/normalizasyon yardimcilari.

Bu kurallar hem onboarding adimlarinda (ProfileCompletionStep*) hem de toplu
guncellemede (UserProfileUpdate) gecerli. Daha once yalnizca adim DTO'larinda
tanimliydiklari icin PUT /profile/update uzerinden normalize edilmemis veri
kaydedilebiliyordu (orn. semasiz website, bastaki @ ile sosyal medya adi).
"""

import re

# URL ve renk desenleri modul seviyesinde derleniyor; her cagrida yeniden
# derlenmesine gerek yok.
_URL_PATTERN = re.compile(
    r"^https?://"
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|"
    r"localhost|"
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"
    r"(?::\d+)?"
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)

_HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")

_USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")

_IMAGE_URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)
_CSS_UNSAFE_PATTERN = re.compile(r"[\"'()\\]")

# Sifre kurallari. TEK KAYNAK burasi: kayit, admin panelinden olusturma/
# guncelleme, sifre sifirlama ve sifre degistirme ayni kuraldan geciyor.
#
# ONCEDEN AYRISMISTI: her DTO kendi min_length=6 degerini tasiyordu, kayit
# formu ise 8 karakter + buyuk/kucuk harf + rakam istiyordu. Kullanici
# formda reddedilen bir sifreyi baska bir uctan (orn. sifre sifirlama)
# sorunsuz belirleyebiliyordu.
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 50

VALID_BACKGROUND_TYPES = ("color", "gradient", "image")

# Profil sayfasi /{username} adresinde yayinlandigi icin frontend'in kendi
# rotalariyla cakisan adlar alinamamali. Aksi halde ornegin "dashboard"
# kullanici adini alan birinin sayfasina hicbir zaman ulasilamaz.
#
# Liste link-yo-self-fe'deki src/app/[language]/ altindaki rotalardan ve
# genel amacli ayrilmis adlardan olusuyor.
RESERVED_USERNAMES = frozenset(
    {
        # Genel
        "admin",
        "api",
        "www",
        "mail",
        "support",
        "help",
        "blog",
        "news",
        "root",
        "static",
        "assets",
        # Frontend rotalari
        "about",
        "admin-panel",
        "analytics",
        "confirm-email",
        "confirm-new-email",
        "contact",
        "dashboard",
        "forgot-password",
        "landing-page",
        "links",
        "onboarding",
        "password-change",
        "privacy-policy",
        "profile",
        "settings",
        "sign-in",
        "sign-up",
    }
)


def validate_username(username: str) -> str:
    """Kullanici adini dogrular ve kucuk harfe cevirir."""
    # NOT: fullmatch kullaniliyor. Onceki hali re.match ile bastan esliyordu,
    # bu yuzden "kaan!!!" gibi degerler gecerli sayiliyordu.
    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError(
            "Username can only contain letters, numbers, dots, hyphens, and underscores"
        )

    if username.lower() in RESERVED_USERNAMES:
        raise ValueError("This username is reserved")

    return username.lower()


def normalize_website(website: str | None) -> str | None:
    """Website adresini mutlak hale getirir ve bicimini dogrular.

    Sema verilmemisse https:// ekleniyor; boylece frontend degeri dogrudan
    href'e koyabiliyor (semasiz deger tarayicida goreli yol sayilir).
    """
    if not website:
        return website

    if not website.startswith(("http://", "https://")):
        website = "https://" + website

    if not _URL_PATTERN.match(website):
        raise ValueError("Invalid website URL")

    return website


def clean_social_handle(username: str | None) -> str | None:
    """Sosyal medya kullanici adindan bastaki @ isaretini ve boslugu temizler."""
    if not username:
        return username

    # Sira onemli: once bosluk kirpilmazsa "  @kaan" gibi bir degerde
    # lstrip("@") hicbir sey yapmaz ve @ hayatta kalir.
    return username.strip().lstrip("@").strip()


def validate_hex_color(color: str | None) -> str | None:
    """Hex renk kodunu dogrular. Bos deger oldugu gibi doner."""
    if not color:
        return color

    # NOT: fullmatch. Onceki hali re.match idi ve "#1383ebZZZZ" gibi
    # degerleri gecerli sayiyordu.
    if not _HEX_COLOR_PATTERN.fullmatch(color):
        raise ValueError("Color must be a valid hex code (e.g., #FF5733)")

    return color


def validate_background_type(background_type: str | None) -> str | None:
    """Arka plan tipini dogrular. Bos deger oldugu gibi doner."""
    if not background_type:
        return background_type

    if background_type not in VALID_BACKGROUND_TYPES:
        raise ValueError(
            f"Background type must be one of: {list(VALID_BACKGROUND_TYPES)}"
        )

    return background_type


def validate_background_value(
    background_type: str | None, background_value: str | None
) -> str | None:
    """Arka plan degeri, tipiyle uyumlu mu?

    Kurallar public profil sayfasinin GERCEKTEN cizebildigi degerleri
    yansitiyor (link-yo-self-fe .../[username]/page-content.tsx):
      - color / gradient: hex renk
      - image: http(s) adresi; tirnak, parantez ve ters bolu yasak, cunku
        deger CSS'e `url(...)` icinde giriyor ve stil enjeksiyonuna acik olur

    Sayfa zaten kendini koruyup gecersiz degerde varsayilana dusuyordu; ama
    bu sessizce oluyordu: kullanici "kaydedildi" mesajini aliyor, sonra
    sayfasinda hicbir sey degismedigini goruyordu. Kural artik kayit
    sirasinda uygulaniyor.

    Ikisinden biri gonderilmemisse dogrulama yapilmiyor: kismi guncellemede
    (PUT /profile/update) yalnizca bir alan degistirilmis olabilir ve diger
    alanin kayitli degeri burada bilinmiyor.
    """
    if not background_type or not background_value:
        return background_value

    if background_type == "image":
        if not _IMAGE_URL_PATTERN.match(background_value):
            raise ValueError(
                "Background image must be an http(s) URL"
            )
        if _CSS_UNSAFE_PATTERN.search(background_value):
            raise ValueError(
                "Background image URL cannot contain quotes, parentheses "
                "or backslashes"
            )
        return background_value

    # color ve gradient duz renk bekliyor (gradient'te ikinci renk
    # theme_color'dan geliyor).
    if not _HEX_COLOR_PATTERN.fullmatch(background_value):
        raise ValueError("Background value must be a valid hex code (e.g., #FF5733)")

    return background_value


def validate_password(password: str) -> str:
    """Sifre kurallarini uygular.

    Kurallar yalnizca YENI sifreler icin gecerli; giris sirasinda mevcut
    sifreler yeniden dogrulanmiyor, yani kural sikilastiginda eski
    kullanicilar disarida kalmiyor.
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {PASSWORD_MIN_LENGTH} characters long"
        )
    if len(password) > PASSWORD_MAX_LENGTH:
        raise ValueError(
            f"Password must be at most {PASSWORD_MAX_LENGTH} characters long"
        )

    if not any(c.islower() for c in password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not any(c.isupper() for c in password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not any(c.isdigit() for c in password):
        raise ValueError("Password must contain at least one number")

    return password

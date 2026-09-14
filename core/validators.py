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

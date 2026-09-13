"""Public profil sayfasi icin DTO'lar.

Bu modeller kimlik dogrulamasi olmadan servis edildigi icin hassas alanlar
(e-posta, id, is_admin, onboarding durumu vb.) bilincli olarak disarida
birakilmistir.
"""

from pydantic import BaseModel, ConfigDict


class PublicLink(BaseModel):
    """Public sayfada gosterilen link. click_count disarida birakildi."""

    id: int
    title: str
    url: str
    description: str | None = None
    icon_url: str | None = None
    background_color: str | None = None
    text_color: str | None = None
    border_radius: int = 8
    order_index: int = 0

    model_config = ConfigDict(from_attributes=True)


class PublicProfile(BaseModel):
    """Bir kullanicinin herkese acik link sayfasi."""

    username: str
    display_name: str
    bio: str | None = None
    profile_image_url: str | None = None

    page_title: str | None = None
    page_description: str | None = None
    website: str | None = None

    twitter_username: str | None = None
    instagram_username: str | None = None
    linkedin_username: str | None = None

    theme_color: str | None = None
    background_type: str | None = None
    background_value: str | None = None

    links: list[PublicLink] = []

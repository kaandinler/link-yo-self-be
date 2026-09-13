"""Public profil sayfasi icin DTO'lar.

Bu modeller kimlik dogrulamasi olmadan servis edildigi icin hassas alanlar
(e-posta, id, is_admin, onboarding durumu vb.) bilincli olarak disarida
birakilmistir.
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class PublicLink(BaseModel):
    """Public sayfada gosterilen link. click_count disarida birakildi."""

    id: int
    title: str
    url: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    border_radius: int = 8
    order_index: int = 0

    model_config = ConfigDict(from_attributes=True)


class PublicProfile(BaseModel):
    """Bir kullanicinin herkese acik link sayfasi."""

    username: str
    display_name: str
    bio: Optional[str] = None
    profile_image_url: Optional[str] = None

    page_title: Optional[str] = None
    page_description: Optional[str] = None
    website: Optional[str] = None

    twitter_username: Optional[str] = None
    instagram_username: Optional[str] = None
    linkedin_username: Optional[str] = None

    theme_color: Optional[str] = None
    background_type: Optional[str] = None
    background_value: Optional[str] = None

    links: List[PublicLink] = []

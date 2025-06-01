from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re

class LinkCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255, description="Link title")
    url: str = Field(..., min_length=1, max_length=2048, description="Link URL")
    description: Optional[str] = Field(None, max_length=500, description="Link description")
    icon_url: Optional[str] = Field(None, max_length=500, description="Link icon URL")
    background_color: Optional[str] = Field(None, max_length=20, description="Background color (hex)")
    text_color: Optional[str] = Field(None, max_length=20, description="Text color (hex)")
    border_radius: Optional[int] = Field(8, ge=0, le=50, description="Border radius in pixels")
    is_active: Optional[bool] = Field(True, description="Whether the link is active")

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, url: str) -> str:
        # URL formatını kontrol et
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        # Basit URL regex kontrolü
        url_pattern = re.compile(
            r'^https?://'  # http:// veya https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
            r'(?::\d+)?'  # optional port
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if not url_pattern.match(url):
            raise ValueError("Invalid URL format")

        return url

    @field_validator("background_color", "text_color", mode="before")
    @classmethod
    def validate_color(cls, color: Optional[str]) -> Optional[str]:
        if color is None:
            return color

        # Hex renk kodu kontrolü
        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValueError("Color must be a valid hex code (e.g., #FF5733)")

        return color


class LinkUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    url: Optional[str] = Field(None, min_length=1, max_length=2048)
    description: Optional[str] = Field(None, max_length=500)
    icon_url: Optional[str] = Field(None, max_length=500)
    background_color: Optional[str] = Field(None, max_length=20)
    text_color: Optional[str] = Field(None, max_length=20)
    border_radius: Optional[int] = Field(None, ge=0, le=50)
    is_active: Optional[bool] = None

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, url: Optional[str]) -> Optional[str]:
        if url is None:
            return url

        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url

        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)

        if not url_pattern.match(url):
            raise ValueError("Invalid URL format")

        return url

    @field_validator("background_color", "text_color", mode="before")
    @classmethod
    def validate_color(cls, color: Optional[str]) -> Optional[str]:
        if color is None:
            return color

        if not re.match(r'^#[0-9A-Fa-f]{6}$', color):
            raise ValueError("Color must be a valid hex code (e.g., #FF5733)")

        return color


class LinkRead(BaseModel):
    id: int
    user_id: int
    title: str
    url: str
    description: Optional[str] = None
    icon_url: Optional[str] = None
    background_color: Optional[str] = None
    text_color: Optional[str] = None
    border_radius: int = 8
    is_active: bool = True
    click_count: int = 0
    order_index: int = 0
    created_at: str
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class LinkReorderRequest(BaseModel):
    link_ids: list[int] = Field(..., description="Ordered list of link IDs")

    @field_validator("link_ids")
    @classmethod
    def validate_link_ids(cls, link_ids: list[int]) -> list[int]:
        if len(link_ids) == 0:
            raise ValueError("Link IDs list cannot be empty")

        if len(link_ids) != len(set(link_ids)):
            raise ValueError("Duplicate link IDs are not allowed")

        return link_ids


class LinkAnalytics(BaseModel):
    link_id: int
    title: str
    url: str
    click_count: int
    created_at: str

    class Config:
        from_attributes = True
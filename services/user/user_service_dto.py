from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)

from core.validators import (
    clean_social_handle,
    normalize_website,
    validate_background_type,
    validate_hex_color,
    validate_username,
)


class UserCreateMinimal(BaseModel):
    """Minimal registration - sadece gerekli alanlar"""
    username: str = Field(..., min_length=3, max_length=30, description="Unique username for profile URL")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, max_length=50, description="User password")

    @field_validator("username", mode="before")
    @classmethod
    def check_username(cls, username: str) -> str:
        """Username validation - kurallar core.validators icinde."""
        return validate_username(username)

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, password: str) -> str:
        """Basic password validation"""
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        if len(password) > 50:
            raise ValueError("Password must be at most 50 characters long")
        return password


class ProfileCompletionStep1(BaseModel):
    """Step 1: Basic Profile Info"""
    first_name: str | None = Field(None, max_length=50, description="First name")
    last_name: str | None = Field(None, max_length=50, description="Last name")
    display_name: str | None = Field(None, max_length=100, description="Display name on profile page")
    bio: str | None = Field(None, max_length=500, description="Short bio/description")
    profile_image_url: str | None = Field(None, max_length=500, description="Profile image URL")


class ProfileCompletionStep2(BaseModel):
    """Step 2: Page Settings"""
    page_title: str | None = Field(None, max_length=100, description="Custom page title")
    page_description: str | None = Field(None, max_length=500, description="Page meta description")
    website: str | None = Field(None, max_length=500, description="Personal/business website")

    @field_validator("website", mode="before")
    @classmethod
    def check_website(cls, website: str | None) -> str | None:
        return normalize_website(website)


class ProfileCompletionStep3(BaseModel):
    """Step 3: Social Media Links"""
    twitter_username: str | None = Field(None, max_length=100, description="Twitter username (without @)")
    instagram_username: str | None = Field(None, max_length=100, description="Instagram username (without @)")
    linkedin_username: str | None = Field(None, max_length=100, description="LinkedIn username")

    @field_validator("twitter_username", "instagram_username", "linkedin_username", mode="before")
    @classmethod
    def check_social_handle(cls, username: str | None) -> str | None:
        return clean_social_handle(username)


class ProfileCompletionStep4(BaseModel):
    """Step 4: Theme & Appearance"""
    theme_color: str | None = Field("#1383eb", max_length=20, description="Primary theme color")
    background_type: str | None = Field("color", description="Background type: color, gradient, image")
    background_value: str | None = Field("#ffffff", max_length=500, description="Background color/image URL")

    @field_validator("theme_color", mode="before")
    @classmethod
    def check_color(cls, color: str | None) -> str | None:
        # Onboarding adiminda bos birakilan alan varsayilana duser.
        return validate_hex_color(color) or "#1383eb"

    @field_validator("background_type", mode="before")
    @classmethod
    def check_background_type(cls, bg_type: str | None) -> str | None:
        return validate_background_type(bg_type) or "color"


class UserProfileUpdate(BaseModel):
    """Complete profile update - all optional"""
    first_name: str | None = Field(None, max_length=50)
    last_name: str | None = Field(None, max_length=50)
    display_name: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=500)
    profile_image_url: str | None = Field(None, max_length=500)
    page_title: str | None = Field(None, max_length=100)
    page_description: str | None = Field(None, max_length=500)
    website: str | None = Field(None, max_length=500)
    twitter_username: str | None = Field(None, max_length=100)
    instagram_username: str | None = Field(None, max_length=100)
    linkedin_username: str | None = Field(None, max_length=100)
    theme_color: str | None = Field(None, max_length=20)
    background_type: str | None = Field(None)
    background_value: str | None = Field(None, max_length=500)

    # NOT: Bu DTO'da hic validator yoktu. Adim adim onboarding uclari degeri
    # normalize ederken PUT /profile/update etmiyordu; sonucta semasiz website
    # ("ornek.com") ve bastaki @ ile sosyal medya adi kaydedilebiliyor, renk
    # ve arka plan tipi hic dogrulanmiyordu. Artik ayni kurallar gecerli.
    #
    # Adim DTO'larindan farki: burada bos birakilan alan varsayilana dusmez,
    # None olarak kalir - kismi guncellemede dokunulmayan alanlar bozulmasin.

    @field_validator("website", mode="before")
    @classmethod
    def check_website(cls, website: str | None) -> str | None:
        return normalize_website(website)

    @field_validator(
        "twitter_username", "instagram_username", "linkedin_username", mode="before"
    )
    @classmethod
    def check_social_handle(cls, username: str | None) -> str | None:
        return clean_social_handle(username)

    @field_validator("theme_color", mode="before")
    @classmethod
    def check_color(cls, color: str | None) -> str | None:
        return validate_hex_color(color)

    @field_validator("background_type", mode="before")
    @classmethod
    def check_background_type(cls, bg_type: str | None) -> str | None:
        return validate_background_type(bg_type)


class UserRead(BaseModel):
    """User read model - session-detached safe"""
    id: int
    username: str
    email: EmailStr
    first_name: str | None = None
    last_name: str | None = None
    display_name: str | None = None
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
    profile_completed: bool = False
    onboarding_completed: bool = False

    # DateTime fields as strings
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Computed field - profile completion percentage
    @computed_field
    @property
    def profile_completion_percentage(self) -> int:
        """Calculate profile completion percentage without accessing relationships"""
        total_fields = 7  # Reduced from 8 since we can't access links
        completed_fields = 0

        # Check required completion fields
        if self.display_name: completed_fields += 1
        if self.bio: completed_fields += 1
        if self.profile_image_url: completed_fields += 1
        if self.website: completed_fields += 1
        if self.twitter_username or self.instagram_username or self.linkedin_username: completed_fields += 1
        if self.page_title: completed_fields += 1
        if self.page_description: completed_fields += 1
        # Note: Link sayısını burada kontrol edemiyoruz çünkü relationship'e erişemiyoruz

        return int((completed_fields / total_fields) * 100)

    # Pydantic v2: datetime alanlari varsayilan olarak ISO 8601 serilestiriliyor,
    # ayrica json_encoders gerekmiyor (v2'de deprecated).
    model_config = ConfigDict(from_attributes=True)


class OnboardingStatus(BaseModel):
    """Onboarding durumu"""
    step: int = 1  # Hangi adımda
    completed_steps: list[int] = []
    profile_completion_percentage: int = 0
    next_step_title: str | None = None
    can_skip: bool = True


# Legacy support - eski UserCreate'i UserCreateMinimal'a yönlendir
UserCreate = UserCreateMinimal
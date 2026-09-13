from datetime import datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    field_validator,
)


class UserCreateMinimal(BaseModel):
    """Minimal registration - sadece gerekli alanlar"""
    username: str = Field(..., min_length=3, max_length=30, description="Unique username for profile URL")
    email: EmailStr = Field(..., description="User email address")
    password: str = Field(..., min_length=6, max_length=50, description="User password")

    @field_validator("username", mode="before")
    @classmethod
    def validate_username(cls, username: str) -> str:
        """Username validation"""
        import re

        # Only alphanumeric, dots, hyphens, underscores allowed
        if not re.match(r'^[a-zA-Z0-9_.-]+', username):
            raise ValueError("Username can only contain letters, numbers, dots, hyphens, and underscores")

        # Reserved usernames
        reserved = ['admin', 'api', 'www', 'mail', 'support', 'help', 'about', 'contact', 'blog', 'news']
        if username.lower() in reserved:
            raise ValueError("This username is reserved")

        return username.lower()

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
    def validate_website(cls, website: str | None) -> str | None:
        if not website:
            return website

        if not website.startswith(('http://', 'https://')):
            website = 'https://' + website

        import re
        url_pattern = re.compile(
            r'^https?://'
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
            r'localhost|'
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
            r'(?::\d+)?'
            r'(?:/?|[/?]\S+)', re.IGNORECASE)

        if not url_pattern.match(website):
            raise ValueError("Invalid website URL")

        return website


class ProfileCompletionStep3(BaseModel):
    """Step 3: Social Media Links"""
    twitter_username: str | None = Field(None, max_length=100, description="Twitter username (without @)")
    instagram_username: str | None = Field(None, max_length=100, description="Instagram username (without @)")
    linkedin_username: str | None = Field(None, max_length=100, description="LinkedIn username")

    @field_validator("twitter_username", "instagram_username", "linkedin_username", mode="before")
    @classmethod
    def clean_username(cls, username: str | None) -> str | None:
        if not username:
            return username
        # Remove @ symbol if present
        return username.lstrip('@').strip()


class ProfileCompletionStep4(BaseModel):
    """Step 4: Theme & Appearance"""
    theme_color: str | None = Field("#1383eb", max_length=20, description="Primary theme color")
    background_type: str | None = Field("color", description="Background type: color, gradient, image")
    background_value: str | None = Field("#ffffff", max_length=500, description="Background color/image URL")

    @field_validator("theme_color", mode="before")
    @classmethod
    def validate_color(cls, color: str | None) -> str | None:
        if not color:
            return "#1383eb"  # Default color

        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}', color):
            raise ValueError("Color must be a valid hex code (e.g., #FF5733)")

        return color

    @field_validator("background_type", mode="before")
    @classmethod
    def validate_background_type(cls, bg_type: str | None) -> str | None:
        if not bg_type:
            return "color"

        valid_types = ["color", "gradient", "image"]
        if bg_type not in valid_types:
            raise ValueError(f"Background type must be one of: {valid_types}")

        return bg_type


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
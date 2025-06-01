from pydantic import BaseModel, EmailStr, Field, field_validator, computed_field
from typing import Optional
from datetime import datetime


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
    first_name: Optional[str] = Field(None, max_length=50, description="First name")
    last_name: Optional[str] = Field(None, max_length=50, description="Last name")
    display_name: Optional[str] = Field(None, max_length=100, description="Display name on profile page")
    bio: Optional[str] = Field(None, max_length=500, description="Short bio/description")
    profile_image_url: Optional[str] = Field(None, max_length=500, description="Profile image URL")


class ProfileCompletionStep2(BaseModel):
    """Step 2: Page Settings"""
    page_title: Optional[str] = Field(None, max_length=100, description="Custom page title")
    page_description: Optional[str] = Field(None, max_length=500, description="Page meta description")
    website: Optional[str] = Field(None, max_length=500, description="Personal/business website")

    @field_validator("website", mode="before")
    @classmethod
    def validate_website(cls, website: Optional[str]) -> Optional[str]:
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
    twitter_username: Optional[str] = Field(None, max_length=100, description="Twitter username (without @)")
    instagram_username: Optional[str] = Field(None, max_length=100, description="Instagram username (without @)")
    linkedin_username: Optional[str] = Field(None, max_length=100, description="LinkedIn username")

    @field_validator("twitter_username", "instagram_username", "linkedin_username", mode="before")
    @classmethod
    def clean_username(cls, username: Optional[str]) -> Optional[str]:
        if not username:
            return username
        # Remove @ symbol if present
        return username.lstrip('@').strip()


class ProfileCompletionStep4(BaseModel):
    """Step 4: Theme & Appearance"""
    theme_color: Optional[str] = Field("#1383eb", max_length=20, description="Primary theme color")
    background_type: Optional[str] = Field("color", description="Background type: color, gradient, image")
    background_value: Optional[str] = Field("#ffffff", max_length=500, description="Background color/image URL")

    @field_validator("theme_color", mode="before")
    @classmethod
    def validate_color(cls, color: Optional[str]) -> Optional[str]:
        if not color:
            return "#1383eb"  # Default color

        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}', color):
            raise ValueError("Color must be a valid hex code (e.g., #FF5733)")

        return color

    @field_validator("background_type", mode="before")
    @classmethod
    def validate_background_type(cls, bg_type: Optional[str]) -> Optional[str]:
        if not bg_type:
            return "color"

        valid_types = ["color", "gradient", "image"]
        if bg_type not in valid_types:
            raise ValueError(f"Background type must be one of: {valid_types}")

        return bg_type


class UserProfileUpdate(BaseModel):
    """Complete profile update - all optional"""
    first_name: Optional[str] = Field(None, max_length=50)
    last_name: Optional[str] = Field(None, max_length=50)
    display_name: Optional[str] = Field(None, max_length=100)
    bio: Optional[str] = Field(None, max_length=500)
    profile_image_url: Optional[str] = Field(None, max_length=500)
    page_title: Optional[str] = Field(None, max_length=100)
    page_description: Optional[str] = Field(None, max_length=500)
    website: Optional[str] = Field(None, max_length=500)
    twitter_username: Optional[str] = Field(None, max_length=100)
    instagram_username: Optional[str] = Field(None, max_length=100)
    linkedin_username: Optional[str] = Field(None, max_length=100)
    theme_color: Optional[str] = Field(None, max_length=20)
    background_type: Optional[str] = Field(None)
    background_value: Optional[str] = Field(None, max_length=500)


class UserRead(BaseModel):
    """User read model - session-detached safe"""
    id: int
    username: str
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    display_name: Optional[str] = None
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
    profile_completed: bool = False
    onboarding_completed: bool = False

    # DateTime fields as strings
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

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

    class Config:
        from_attributes = True
        # DateTime serialization için
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }


class OnboardingStatus(BaseModel):
    """Onboarding durumu"""
    step: int = 1  # Hangi adımda
    completed_steps: list[int] = []
    profile_completion_percentage: int = 0
    next_step_title: Optional[str] = None
    can_skip: bool = True


# Legacy support - eski UserCreate'i UserCreateMinimal'a yönlendir
UserCreate = UserCreateMinimal
from pydantic import BaseModel, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    username: str = Field(..., min_length=4, max_length=50, description="Username must be unique and between 4 and 50 characters long")
    email: EmailStr = Field(..., min_length=3, max_length=50, description="User email")
    password: str = Field(..., min_length=6, max_length=50, description="Password must contain at least one uppercase letter, one lowercase letter, one digit, and one special character")
    profile_image_url: str | None = Field(None, max_length=255, description="User profile image URL")

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, password: str) -> str:
        if len(password) < 6:
            raise ValueError("Password must be at least 6 characters long")
        if len(password) > 50:
            raise ValueError("Password must be at most 50 characters long")
        if not any(char.isupper() for char in password):
            raise ValueError("Password must contain at least one uppercase letter")
        if not any(char.islower() for char in password):
            raise ValueError("Password must contain at least one lowercase letter")
        if not any(char.isdigit() for char in password):
            raise ValueError("Password must contain at least one digit")
        if not any(char in "!@#$%^&*()-_=+[]{}|;:'\",.<>?/" for char in password):
            raise ValueError("Password must contain at least one special character")

        return password


class UserInDB(BaseModel):
    id: int
    username: str
    email: EmailStr
    hashed_password: str

    class Config:
        orm_mode = True


class Token(BaseModel):
    access_token: str
    token_type: str  # bearer


class TokenData(BaseModel):
    username: str | None = None


class UserRead(BaseModel):
    id: int | None = Field(None, description="User ID")
    username: str | None = Field(None, min_length=4, max_length=50, description="Username must be unique and between 4 and 50 characters long")
    email: EmailStr | None = Field(None, max_length=50, description="User email")
    profile_image_url: str | None = Field(None, max_length=255, description="User profile image URL")

    class Config:
        orm_mode = True

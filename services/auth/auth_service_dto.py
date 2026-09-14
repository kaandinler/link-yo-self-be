# Refresh token şeması
from pydantic import BaseModel, EmailStr, Field


class TokenRefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str = None

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Reset token from the email link")
    password: str = Field(..., min_length=6, max_length=50, description="New password")

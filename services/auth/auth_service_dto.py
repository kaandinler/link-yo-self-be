# Refresh token şeması
from pydantic import BaseModel, EmailStr, Field, field_validator

from core.validators import (
    PASSWORD_MAX_LENGTH,
    PASSWORD_MIN_LENGTH,
    validate_password,
)


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
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="New password",
    )

    @field_validator("password")
    @classmethod
    def check_password(cls, password: str) -> str:
        """Sifre kurallari - tek kaynak core.validators."""
        return validate_password(password)


class ChangePasswordRequest(BaseModel):
    """Giris yapmis kullanicinin kendi sifresini degistirmesi."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
        description="New password",
    )

    @field_validator("new_password")
    @classmethod
    def check_password(cls, password: str) -> str:
        return validate_password(password)


class ChangeEmailRequest(BaseModel):
    """Giris yapmis kullanicinin e-posta adresi degistirme talebi.

    Sifre onayi sart: e-posta, sifre sifirlama baglantisinin gittigi adres.
    Acik birakilmis bir oturum bunu tek basina degistirebilseydi hesabi ele
    gecirmenin yolu olurdu.
    """

    password: str = Field(..., min_length=1, description="Current password")
    new_email: EmailStr = Field(..., description="New email address")


class EmailChangeRequested(BaseModel):
    """Adres degisikligi talebinin yaniti.

    Adres henuz degismedi; yalnizca bu adrese dogrulama baglantisi gonderildi.
    """

    pending_email: EmailStr


class VerifyEmailRequest(BaseModel):
    token: str = Field(..., min_length=1, description="Token from the email link")

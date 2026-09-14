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


class ChangePasswordRequest(BaseModel):
    """Giris yapmis kullanicinin kendi sifresini degistirmesi."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, max_length=50, description="New password")


class ChangeEmailRequest(BaseModel):
    """Giris yapmis kullanicinin e-posta adresini degistirmesi.

    Sifre onayi sart: e-posta, sifre sifirlama baglantisinin gittigi adres.
    Acik birakilmis bir oturum bunu tek basina degistirebilseydi hesabi ele
    gecirmenin yolu olurdu.
    """

    password: str = Field(..., min_length=1, description="Current password")
    new_email: EmailStr = Field(..., description="New email address")

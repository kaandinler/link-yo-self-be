from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status


class BaseAppException(HTTPException):
    """
    Ana uygulama exception sınıfı. Tüm özel uygulama istisnaları bu sınıftan türetilmelidir.
    """
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail: str = "Unknown error occurred."
    headers: Optional[Dict[str, Any]] = None

    def __init__(
        self,
        detail: Optional[str] = None,
        headers: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Args:
            detail: Hata ile ilgili açıklama
            headers: HTTP yanıt başlıkları
            **kwargs: Ek bağlam bilgileri (hata mesajına eklenebilir)
        """
        self.extra_info = kwargs

        # Eğer detay verilmişse, sınıfın varsayılan değeri yerine onu kullan
        actual_detail = detail if detail is not None else self.detail

        # Eğer ek bilgiler varsa ve detay bir string ise, detayı zenginleştir
        if self.extra_info and isinstance(actual_detail, str):
            actual_detail = (f"{actual_detail} Extra info: {self.extra_info}")

        # Eğer headers verilmişse, sınıfın varsayılan değeri yerine onu kullan
        actual_headers = headers if headers is not None else self.headers

        # Ana sınıfın __init__ metodunu çağır
        super().__init__(
            status_code=self.status_code,
            detail=actual_detail,
            headers=actual_headers
        )


class NotAuthenticatedException(BaseAppException):
    """Kullanıcı kimlik doğrulama hatası"""
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Unauthenticated user"
    headers = {"WWW-Authenticate": "Bearer"}


class PermissionDeniedException(BaseAppException):
    """Yetki hatası"""
    status_code = status.HTTP_403_FORBIDDEN
    detail = "Permission denied"


class NotFoundException(BaseAppException):
    """Kaynak bulunamadı hatası"""
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Resource not found"


class AlreadyExistsException(BaseAppException):
    """Kaynak zaten var hatası"""
    status_code = status.HTTP_409_CONFLICT
    detail ="Resource already exists"


class ValidationException(BaseAppException):
    """Veri doğrulama hatası"""
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    detail = "Validation error"

    def __init__(
        self,
        detail: Optional[str] = None,
        errors: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ):
        """
        Args:
            detail: Hata ile ilgili genel açıklama
            errors: Doğrulama hatalarının listesi
            **kwargs: Ek bağlam bilgileri
        """
        if errors:
            # errors listesi varsa, detail'i dinamik olarak oluştur
            super().__init__(detail=detail, validation_errors=errors, **kwargs)
        else:
            super().__init__(detail=detail, **kwargs)


class DatabaseException(BaseAppException):
    """Veritabanı hatası"""
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "Error occurred while accessing the database."


class ExternalServiceException(BaseAppException):
    """Dış servis hatası"""
    status_code = status.HTTP_502_BAD_GATEWAY
    detail = "External service error occurred."


class RateLimitException(BaseAppException):
    """İstek limiti aşıldı hatası"""
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    detail = "Rate limit exceeded. Please try again later."

    def __init__(
        self,
        detail: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Args:
            detail: Hata ile ilgili açıklama
            retry_after: Kaç saniye sonra tekrar denenmesi gerektiği
            **kwargs: Ek bağlam bilgileri
        """
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(detail=detail, headers=headers, **kwargs)


class ServiceUnavailableException(BaseAppException):
    """Servis kullanılamıyor hatası"""
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "Service unavailable. Please try again later."

    def __init__(
        self,
        detail: Optional[str] = None,
        retry_after: Optional[int] = None,
        **kwargs
    ):
        """
        Args:
            detail: Hata ile ilgili açıklama
            retry_after: Kaç saniye sonra tekrar denenmesi gerektiği
            **kwargs: Ek bağlam bilgileri
        """
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(detail=detail, headers=headers, **kwargs)

# Login credentials exception
class InvalidCredentialsException(BaseAppException):
    """Geçersiz kimlik bilgileri hatası"""
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Invalid credentials provided."
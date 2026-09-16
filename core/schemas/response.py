from enum import StrEnum
from typing import Any, Generic, TypeVar, Union

from pydantic import BaseModel, Field

# Tip değişkeni, herhangi bir veri tipi için
T = TypeVar('T')


class ResponseStatus(StrEnum):
    """API yanıtı için durum enumu.

    StrEnum (py311+): (str, Enum) karisimindan farki, str(uye) ve f-string
    ciktisinin "ResponseStatus.SUCCESS" degil "success" olmasi. Pydantic
    zaten .value ile serilestirdigi icin JSON ciktisi degismiyor.
    """
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class BaseResponseModel(BaseModel, Generic[T]):
    """
    Tüm API yanıtları için temel model.

    Özellikler:
        status: Yanıt durumu (success, error, warning, info)
        message: İsteğe bağlı açıklayıcı mesaj
        data: İsteğe bağlı yanıt verisi
    """
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)
    message: str | None = Field(default=None, description="İsteğe bağlı açıklayıcı mesaj")
    data: T | None = Field(default=None, description="Yanıt verisi")


class PaginatedResponseModel(BaseResponseModel, Generic[T]):
    """
    Sayfalandırılmış API yanıtları için model.

    Ek Özellikler:
        meta: Sayfalandırma meta bilgileri
    """
    data: list[T] | None = Field(default=None)
    meta: dict[str, Any] | None = Field(
        default=None,
        description="Sayfalandırma meta bilgileri: toplam, sayfa, sayfa_boyutu vb."
    )


class ErrorResponseModel(BaseResponseModel):
    """
    Hata yanıtları için özel model.

    Ek Özellikler:
        errors: Doğrulama hatalarının ayrıntılı listesi
    """
    status: ResponseStatus = Field(default=ResponseStatus.ERROR)
    errors: list[dict[str, Any]] | None = Field(
        default=None,
        description="Doğrulama hataları listesi"
    )


class SuccessResponse(BaseResponseModel[T]):
    """Başarılı yanıt için yardımcı sınıf"""
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)

    @classmethod
    def create(
        cls, data: T | None = None, message: str | None = None
    ) -> "SuccessResponse":
        """Başarılı bir yanıt oluşturur"""
        return cls(
            status=ResponseStatus.SUCCESS,
            message=message,
            data=data
        )


class ErrorResponse(BaseResponseModel):
    """Hata yanıtı için yardımcı sınıf"""
    status: ResponseStatus = Field(default=ResponseStatus.ERROR)

    @classmethod
    def create(
        cls,
        message: str,
        data: Any = None,
        errors: list[dict[str, Any]] | None = None
    ) -> Union["ErrorResponse", "ErrorResponseModel"]:
        """Hata yanıtı oluşturur"""
        if errors:
            return ErrorResponseModel(
                status=ResponseStatus.ERROR,
                message=message,
                data=data,
                errors=errors
            )
        return cls(
            status=ResponseStatus.ERROR,
            message=message,
            data=data
        )

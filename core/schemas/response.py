from enum import Enum
from typing import Any, Generic, List, Optional, TypeVar, Dict, Union

from pydantic import BaseModel, Field

# Tip değişkeni, herhangi bir veri tipi için
T = TypeVar('T')


class ResponseStatus(str, Enum):
    """API yanıtı için durum enumu"""
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
    message: Optional[str] = Field(default=None, description="İsteğe bağlı açıklayıcı mesaj")
    data: Optional[T] = Field(default=None, description="Yanıt verisi")


class PaginatedResponseModel(BaseResponseModel, Generic[T]):
    """
    Sayfalandırılmış API yanıtları için model.

    Ek Özellikler:
        meta: Sayfalandırma meta bilgileri
    """
    data: Optional[List[T]] = Field(default=None)
    meta: Optional[Dict[str, Any]] = Field(
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
    errors: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Doğrulama hataları listesi"
    )


class SuccessResponse(BaseResponseModel[T]):
    """Başarılı yanıt için yardımcı sınıf"""
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS)

    @classmethod
    def create(cls, data: T = None, message: str = None) -> "SuccessResponse":
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
        errors: List[Dict[str, Any]] = None
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

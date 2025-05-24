from functools import wraps
from typing import Any, Callable, TypeVar

from fastapi import APIRouter

from core.schemas.response import BaseResponseModel, SuccessResponse

# Tip değişkeni
T = TypeVar('T')


def wrap_response(func: Callable) -> Callable:
    """
    API endpoint fonksiyonunu sarmalar ve yanıtı BaseResponseModel içine alır.

    Args:
        func: Sarmalanacak endpoint fonksiyonu

    Returns:
        Sarmalanan fonksiyon
    """
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> BaseResponseModel:
        # Orijinal fonksiyonu çağır
        result = await func(*args, **kwargs)

        # Sonuç zaten bir BaseResponseModel ise, olduğu gibi döndür
        if isinstance(result, BaseResponseModel):
            return result

        # Sonucu bir BaseResponseModel içine sar
        return SuccessResponse.create(data=result)

    return wrapper


def add_response_model(router: APIRouter) -> APIRouter:
    """
    Router'ın tüm route'larına BaseResponseModel ekler.

    Args:
        router: Güncellenecek APIRouter

    Returns:
        Güncellenen router
    """
    # Router'ın orijinal metotlarını kaydet
    original_methods = {
        "get": router.get,
        "post": router.post,
        "put": router.put,
        "delete": router.delete,
        "patch": router.patch,
        "options": router.options,
        "head": router.head,
        "trace": router.trace,
    }

    # Her bir metot için yeni bir wrapper oluştur
    for method_name, original_method in original_methods.items():
        @wraps(original_method)
        def wrapped_method(*args: Any, **kwargs: Any) -> Callable:
            # response_model parametresini kontrol et
            response_model = kwargs.get("response_model")

            if response_model and not issubclass(response_model, BaseResponseModel):
                # Eğer response_model bir BaseResponseModel değilse, onu BaseResponseModel içine sar
                response_type = response_model
                # kwargs'dan response_model'i kaldır, çünkü yeni bir tane oluşturacağız
                kwargs.pop("response_model", None)

                # Normal fonksiyonu çağır ama response_model olmadan
                route_decorator = original_method(*args, **kwargs)

                # Endpoint fonksiyonunu sarmala
                def decorator(func: Callable) -> Callable:
                    # Endpoint fonksiyonunu BaseResponseModel ile sarmala
                    wrapped_func = wrap_response(func)

                    # Yeni response_model oluştur: BaseResponseModel[OrijinalModel]
                    custom_response_model = BaseResponseModel[response_type]

                    # Orijinal route decorator'ı çağır, ancak sarmalanmış fonksiyon ve yeni model ile
                    return route_decorator(wrapped_func, response_model=custom_response_model)

                return decorator

            # response_model yoksa veya zaten bir BaseResponseModel ise, normal davran
            return original_method(*args, **kwargs)

        # Router'ın ilgili metodunu güncelle
        setattr(router, method_name, wrapped_method)

    return router

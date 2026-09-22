"""Hata yolunun testleri.

NEDEN AYRI BIR DOSYA: core/middleware/error_handler.py kapsamda %58'de
duruyordu ve eksik kalan satirlar tam olarak HATA ANINDA calisan
satirlardi -- yani en az gozlemlenen, en cok guvenilen yol. Olcum
sirasinda oradaki bir BILGI SIZINTISI ortaya cikti (bkz.
TestBeklenmeyenHata).

Uc dal dogrudan cagrilarak test ediliyor. Bunun sebebi kolaycilik
degil: middleware, Starlette yiginenda ExceptionMiddleware'in DISINDA
duruyor, yani `app.exception_handler(...)` ile kayitli bir sinif ona
hic ulasmiyor. Dogrudan cagri, fonksiyonun sozlesmesini yigindaki
yerinden bagimsiz olarak sabitliyor. Yigindan GECEN davranis ise
ayrica TestUygulamaUzerinden'de olculuyor.
"""

import logging

import pytest
from fastapi import FastAPI, status
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

from core.exceptions import NotFoundException, PermissionDeniedException
from core.middleware.error_handler import (
    catch_exceptions_middleware,
    setup_exception_handlers,
)

SIZAN_METIN = "GIZLI_ANAHTAR_abc123 /home/kullanici/ayarlar.py"


def sahte_istek(yol: str = "/deneme", yontem: str = "GET") -> Request:
    return Request(
        {
            "type": "http",
            "method": yontem,
            "path": yol,
            "raw_path": yol.encode(),
            "query_string": b"",
            "headers": [],
        }
    )


def firlatan(hata: Exception):
    """call_next yerine gecen, verilen hatayi firlatan cagrilabilir."""

    async def cagir(_request):
        raise hata

    return cagir


def govde(yanit) -> dict:
    import json

    return json.loads(bytes(yanit.body).decode())


class TestMiddlewareDallari:
    async def test_normal_istek_dokunulmadan_geciyor(self):
        """Once mutlu yolu: middleware araya girmiyor."""
        from fastapi.responses import JSONResponse

        beklenen = JSONResponse({"status": "success"})

        async def cagir(_request):
            return beklenen

        yanit = await catch_exceptions_middleware(sahte_istek(), cagir)

        assert yanit is beklenen

    async def test_uygulama_hatasi_kendi_kodunu_koruyor(self):
        """BaseAppException dali: durum kodu ve detay korunuyor.

        Bu dal normal HTTP akisinda calismiyor (setup_exception_handlers'in
        kaydettigi handler daha icerideki ExceptionMiddleware'de karsiliyor).
        Yine de duruyor, cunku o handler kaldirilirsa uygulama hatalarinin
        500'e dusmemesi gerekiyor -- ve duruyorsa OLCULMELI.
        """
        yanit = await catch_exceptions_middleware(
            sahte_istek(), firlatan(PermissionDeniedException("bu link senin degil"))
        )

        assert yanit.status_code == status.HTTP_403_FORBIDDEN
        assert govde(yanit)["message"] == "bu link senin degil"
        assert govde(yanit)["status"] == "error"

    async def test_uygulama_hatasinin_basliklari_tasiniyor(self):
        """401'in WWW-Authenticate basligi dusmemeli; yoksa istemci
        yeniden kimlik dogrulama akisini baslatamaz."""
        from core.exceptions import NotAuthenticatedException

        yanit = await catch_exceptions_middleware(
            sahte_istek(), firlatan(NotAuthenticatedException())
        )

        assert yanit.status_code == status.HTTP_401_UNAUTHORIZED
        assert yanit.headers.get("www-authenticate") == "Bearer"

    async def test_veritabani_hatasinin_metni_govdeye_gecmiyor(self):
        """SQLAlchemy hatasinin metninde sorgu ve kolon adlari olabilir."""
        yanit = await catch_exceptions_middleware(
            sahte_istek(),
            firlatan(SQLAlchemyError("SELECT hashed_password FROM users WHERE id=1")),
        )

        assert yanit.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert govde(yanit)["message"] == (
            "A database error occurred. Please try again later."
        )
        assert "hashed_password" not in bytes(yanit.body).decode()


class TestBeklenmeyenHata:
    """REGRESYON: beklenmeyen hatanin metni istemciye gidiyordu.

    Onceki hal `message=f"Unexpected error: {exc!s}"` idi. Beklenmeyen
    hata, tam da metni kontrol edilmeyen hatadir: icinde dosya yolu,
    ortam degiskeni, SQL parcasi ya da baska bir kullanicinin verisi
    olabilir. Olculen yanit aynen suydu:

        {"status":"error","message":"Unexpected error: GIZLI_ANAHTAR_abc123
         /home/kullanici/ayarlar.py","data":null}
    """

    async def test_hata_metni_govdeye_sizmiyor(self):
        yanit = await catch_exceptions_middleware(
            sahte_istek(), firlatan(RuntimeError(SIZAN_METIN))
        )

        metin = bytes(yanit.body).decode()

        assert yanit.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "GIZLI_ANAHTAR_abc123" not in metin
        assert "/home/kullanici" not in metin
        assert govde(yanit)["message"] == (
            "An unexpected error occurred. Please try again later."
        )

    async def test_ayrinti_LOGA_yaziliyor(self, caplog):
        """Sizintiyi kapatmak, hatayi kaybetmek anlamina gelmemeli:
        ayrinti sunucu tarafinda tam haliyle duruyor."""
        with caplog.at_level(logging.ERROR, logger="core.middleware.error_handler"):
            await catch_exceptions_middleware(
                sahte_istek(), firlatan(RuntimeError(SIZAN_METIN))
            )

        assert SIZAN_METIN in caplog.text


class TestUygulamaUzerinden:
    """Ayni davranis, gercek Starlette yigininden gecerek."""

    @pytest.fixture
    def uygulama(self):
        app = FastAPI()
        setup_exception_handlers(app)

        @app.get("/db")
        async def db():
            raise SQLAlchemyError("SELECT hashed_password FROM users")

        @app.get("/patla")
        async def patla():
            raise RuntimeError(SIZAN_METIN)

        @app.get("/yok-sayilan")
        async def yok_sayilan():
            raise NotFoundException("gizli link")

        @app.post("/sadece-post")
        async def sadece_post():
            return {}

        return app

    @pytest.fixture
    async def istemci(self, uygulama):
        transport = ASGITransport(app=uygulama, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    async def test_veritabani_hatasi_500_ve_genel_mesaj(self, istemci):
        yanit = await istemci.get("/db")

        assert yanit.status_code == 500
        assert "hashed_password" not in yanit.text
        assert yanit.json()["status"] == "error"

    async def test_beklenmeyen_hata_500_ve_sizinti_yok(self, istemci):
        yanit = await istemci.get("/patla")

        assert yanit.status_code == 500
        assert "GIZLI_ANAHTAR_abc123" not in yanit.text

    async def test_olmayan_yol_ayni_zarfla_404(self, istemci):
        """404 de ham {"detail": ...} degil, uygulamanin zarfiyla donuyor."""
        yanit = await istemci.get("/boyle-bir-yol-yok")

        assert yanit.status_code == 404
        assert yanit.json()["status"] == "error"
        assert yanit.json()["data"] is None
        assert "/boyle-bir-yol-yok" in yanit.json()["message"]

    async def test_yanlis_yontem_405_ve_ayni_zarf(self, istemci):
        yanit = await istemci.get("/sadece-post")

        assert yanit.status_code == 405
        assert yanit.json()["status"] == "error"
        assert "GET" in yanit.json()["message"]

    async def test_uygulama_hatasi_kendi_koduyla_donuyor(self, istemci):
        """404 durum kodlu uygulama hatasi da zarfli donuyor."""
        yanit = await istemci.get("/yok-sayilan")

        assert yanit.status_code == 404
        assert yanit.json()["status"] == "error"

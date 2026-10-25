"""API belgesinin (Swagger, ReDoc, OpenAPI semasi) hangi ortamda acik oldugu.

Uretimde kapali, gelistirmede acik (gerekce: main.belge_adresleri). Bu test
dusserse uretimde butun uclarin haritasi yeniden herkese acilmis demektir.

create_app() BURADA CAGRILMIYOR: DI container'ini modullere yeniden
bagliyor ve sonraki testlerin sahte nesnelerini kopariyor (olculdu:
test_auth.py'de 21 test dustu). Ayar, create_app'in kullandigi yardimci
uzerinden ve o yardimciyla kurulan gercek bir FastAPI uzerinden olculuyor.
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

import main
from settings import settings

BELGE_YOLLARI = ["/docs", "/redoc", "/openapi.json"]


async def _durumlar(app) -> dict[str, int]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as istemci:
        return {yol: (await istemci.get(yol)).status_code for yol in BELGE_YOLLARI}


@pytest.mark.asyncio
async def test_uretimde_belgeler_kapali(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")

    assert main.belge_adresleri() == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }
    assert await _durumlar(FastAPI(**main.belge_adresleri())) == dict.fromkeys(
        BELGE_YOLLARI, 404
    )


@pytest.mark.asyncio
async def test_gelistirmede_belgeler_acik(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")

    assert await _durumlar(FastAPI(**main.belge_adresleri())) == dict.fromkeys(
        BELGE_YOLLARI, 200
    )


@pytest.mark.asyncio
async def test_uygulama_yardimciyi_kullaniyor():
    """create_app gercekten belge_adresleri()'ni kullaniyor mu (testler gelistirmede kosuyor)."""
    assert main.app.openapi_url == "/openapi.json"
    assert await _durumlar(main.app) == dict.fromkeys(BELGE_YOLLARI, 200)

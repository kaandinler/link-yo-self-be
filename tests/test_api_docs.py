"""API belgesinin (Swagger, ReDoc, OpenAPI semasi) hangi ortamda acik oldugu.

Uretimde kapali, gelistirmede acik (gerekce: main.create_app). Bu test
dusserse uretimde butun uclarin haritasi yeniden herkese acilmis demektir.
"""

import pytest
from httpx import ASGITransport, AsyncClient

import main
from settings import settings

BELGE_YOLLARI = ["/docs", "/redoc", "/openapi.json"]


async def _durumlar(app, **basliklar) -> dict[str, int]:
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="https://api.ornek.test"
    ) as istemci:
        return {
            yol: (await istemci.get(yol, headers=basliklar)).status_code
            for yol in BELGE_YOLLARI
        }


@pytest.mark.asyncio
async def test_uretimde_belgeler_kapali(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "allowed_hosts", ["api.ornek.test"])
    monkeypatch.setattr(settings, "allowed_origins", ["https://ornek.test"])

    app = main.create_app()

    assert app.openapi_url is None
    # 404: yol yok. (Host ve https dogru verildi; 400/307 olsaydi test
    # belgeyi degil ara katmanlari olcerdi.)
    assert await _durumlar(app) == dict.fromkeys(BELGE_YOLLARI, 404)


@pytest.mark.asyncio
async def test_gelistirmede_belgeler_acik(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")

    app = main.create_app()

    assert await _durumlar(app) == dict.fromkeys(BELGE_YOLLARI, 200)

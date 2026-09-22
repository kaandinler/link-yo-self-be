"""Test altyapisi.

DIKKAT: Ortam degiskenleri, uygulama modulleri import edilmeden ONCE
ayarlanmali. `settings` modul seviyesinde olusturuluyor ve `di/container.py`
degerleri import aninda okuyor.
"""

import contextlib
import os
import pathlib
import re
import tempfile

TEST_DB_PATH = pathlib.Path(tempfile.gettempdir()) / "linkyoself_test.db"

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TEST_DB_PATH}"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "30"
os.environ["ENVIRONMENT"] = "development"
os.environ["DB_ECHO"] = "false"

# ASAGIDAKI IKISI BILINCLI OLARAK ACIKCA YAZILIYOR.
#
# pydantic-settings once ortam degiskenine, sonra .env dosyasina
# bakiyor. Gelistiricinin .env'inde bu anahtarlardan biri kapaliysa
# (ornegin yerel E2E kosusu icin RATE_LIMIT_ENABLED=false) suit
# sessizce BASKA BIR KODU olcerdi -- olculdu: tam olarak bu oldu ve
# test_rate_limit.py'nin 7 testi dustu. Degerleri burada sabitlemek
# suiti .env'den bagimsiz kiliyor.
os.environ["RATE_LIMIT_ENABLED"] = "true"
os.environ["CLICK_DEDUP_SECONDS"] = "30"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from core.rate_limit import hiz_siniri
from main import app as fastapi_app
from models import Base


@pytest.fixture(scope="session")
def app():
    return fastapi_app


@pytest_asyncio.fixture
async def client(app):
    """Her test icin bos bir veritabani ve ona bagli HTTP istemcisi.

    HIZ SINIRI SAYACLARI DA SIFIRLANIYOR. Sinir testlerde KAPATILMIYOR
    -- kapatsaydik butun testler kodun sinirsiz halini kosar ve
    sinirlayicinin mesru akislari bozup bozmadigini hicbir sey
    olcmezdi. Bunun yerine her test temiz bir sayacla basliyor:
    testler ASGI tasiyicisi uzerinden kostugu icin hepsi ayni istemci
    adresini paylasiyor, sifirlamasaydik bir testin denemeleri
    digerini duserdi.
    """
    hiz_siniri.sifirla()

    engine = app.container.engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def tekillestirme_kapali(monkeypatch):
    """Tiklama tekillestirmesini kapatir.

    NEDEN GEREKLI: tekillestirme IP'ye gore calisiyor ve ASGI
    tasiyicisindaki butun istekler ayni adresten geliyor. "Iki farkli
    kisi tikladi" demek isteyen bir toplama testi, tekillestirme
    acikken aslinda "ayni kisi iki kez tikladi" der ve ikinci tiklama
    sayilmaz.

    Tekillestirmenin KENDISI tests/test_click_dedup.py'de, acikken
    test ediliyor; burada kapatmak kapsamda bosluk birakmiyor.
    """
    from settings import settings as ayarlar

    monkeypatch.setattr(ayarlar, "click_dedup_seconds", 0)


# --- Yardimcilar ---------------------------------------------------------

DEFAULT_USER = {
    "username": "kaan",
    "email": "kaan@example.com",
    "password": "Secret123",
}


async def register_user(client: AsyncClient, **overrides) -> dict:
    """Kullanici kaydeder ve olusan kullanici verisini doner."""
    payload = {**DEFAULT_USER, **overrides}
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def login(
    client: AsyncClient, identifier: str | None = None, password: str | None = None
) -> str:
    """Giris yapar ve access token doner."""
    response = await client.post(
        "/api/v1/auth/token",
        data={
            "username": identifier or DEFAULT_USER["email"],
            "password": password or DEFAULT_USER["password"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def make_admin(app, username: str) -> None:
    """Kullaniciyi admin yapar.

    is_admin API uzerinden set edilemedigi icin (bilincli bir karar) testte
    dogrudan veritabanina yaziliyor.
    """
    from sqlalchemy import update

    from models import User

    session_factory = app.container.async_session_factory()
    async with session_factory() as session:
        await session.execute(
            update(User).where(User.username == username).values(is_admin=True)
        )
        await session.commit()


async def seed_platforms(app, *adlar: str) -> dict[str, int]:
    """Platform satirlari ekler ve {ad: id} doner.

    NEDEN TESTTE EKLENIYOR: platformlar uretimde bir migration ile
    geliyor (a7b8c9d0e1f2_seed_platforms), ama testler migration
    calistirmiyor -- conftest tablolari Base.metadata.create_all ile
    kuruyor, yani platforms tablosu bos basliyor. Uc bos tabloyla
    calisamaz (platform_id bir FOREIGN KEY), bu yuzden sosyal hesap
    testleri ihtiyaci olan platformu kendisi ekliyor.
    """
    from sqlalchemy import select

    from models import Platform

    session_factory = app.container.async_session_factory()
    async with session_factory() as session:
        for ad in adlar:
            session.add(Platform(name=ad, display_name=ad.title()))
        await session.commit()

        sonuc = await session.execute(
            select(Platform.name, Platform.id).where(Platform.name.in_(adlar))
        )
        return {ad: kimlik for ad, kimlik in sonuc.all()}


@pytest_asyncio.fixture
async def auth_client(client):
    """Kayitli ve giris yapmis bir kullanicinin token'ini tasiyan istemci."""
    await register_user(client)
    token = await login(client)
    client.headers.update(auth_header(token))
    yield client


@pytest_asyncio.fixture
async def admin_client(client, app):
    """Admin yetkili, giris yapmis bir kullanicinin token'ini tasiyan istemci."""
    await register_user(client)
    await make_admin(app, DEFAULT_USER["username"])
    token = await login(client)
    client.headers.update(auth_header(token))
    yield client


@contextlib.contextmanager
def yakala_epostalar(app):
    """Gonderilen e-postalari toplar.

    Baglantilardaki ham token yalnizca e-postada bulunuyor (veritabaninda
    ozeti saklaniyor), bu yuzden testte EmailSender.send ciktisini
    yakaliyoruz.
    """
    gonderilen: list[dict] = []
    sender = app.container.email_sender()
    orijinal = sender.send
    sender.send = lambda to, subject, body: gonderilen.append(
        {"to": to, "subject": subject, "body": body}
    )
    try:
        yield gonderilen
    finally:
        sender.send = orijinal


def token_cikar(body: str) -> str:
    """E-posta govdesindeki baglantidan ham token'i alir."""
    match = re.search(r"token=([\w\-]+)", body)
    assert match, f"token bulunamadi: {body}"
    return match.group(1)


async def request_reset_token(client: AsyncClient, app) -> str:
    """Sifre sifirlama talep eder ve e-postaya giden ham token'i doner."""
    with yakala_epostalar(app) as gonderilen:
        response = await client.post(
            "/api/v1/auth/forgot-password", json={"email": DEFAULT_USER["email"]}
        )
        assert response.status_code == 204, response.text

    assert gonderilen, "sifirlama e-postasi gonderilmedi"
    return token_cikar(gonderilen[-1]["body"])

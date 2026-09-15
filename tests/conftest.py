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

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from main import app as fastapi_app
from models import Base


@pytest.fixture(scope="session")
def app():
    return fastapi_app


@pytest_asyncio.fixture
async def client(app):
    """Her test icin bos bir veritabani ve ona bagli HTTP istemcisi."""
    engine = app.container.engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


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

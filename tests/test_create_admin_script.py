"""scripts/create_admin.py - ilk admini acan betik.

NEDEN TEST EDILIYOR: panele girmenin tek yolu admin olmak, admin
yapmanin tek yolu da panele girmek. Bu betik o dongunun disaridan tek
kirilma noktasi; bozulursa bos bir veritabaninda panele kimse
giremez ve bunu ancak kurulum sirasinda fark ederiz.
"""
import pytest
from sqlalchemy import select

from models import User
from scripts.create_admin import admin_olustur
from tests.conftest import DEFAULT_USER, login, register_user

PAROLA = "Admin.Parola1"


async def kullaniciyi_getir(app, username: str) -> User | None:
    fabrika = app.container.async_session_factory()
    async with fabrika() as oturum:
        return (
            await oturum.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()


class TestAdminBetigi:
    async def test_yeni_admin_aciyor(self, client, app):
        sonuc = await admin_olustur("ilkadmin", "ilkadmin@example.com", PAROLA)

        assert "olusturuldu" in sonuc
        kullanici = await kullaniciyi_getir(app, "ilkadmin")
        assert kullanici is not None
        assert kullanici.is_admin is True

    async def test_acilan_admin_giris_yapabiliyor(self, client, app):
        """Parola gercekten hash'lenmis mi -- kayit yeterli degil."""
        await admin_olustur("ilkadmin", "ilkadmin@example.com", PAROLA)

        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "ilkadmin@example.com", "password": PAROLA},
        )

        assert response.status_code == 200, response.text

    async def test_acilan_admin_admin_ucuna_erisebiliyor(self, client, app):
        """Asil olcu bu: bayrak dogru ama uc reddederse betik ise yaramaz."""
        await admin_olustur("ilkadmin", "ilkadmin@example.com", PAROLA)
        token = (
            await client.post(
                "/api/v1/auth/token",
                data={"username": "ilkadmin@example.com", "password": PAROLA},
            )
        ).json()["data"]["access_token"]

        response = await client.get(
            "/api/v1/users/?page=1&limit=5",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200, response.text

    async def test_ikinci_kez_calistirmak_guvenli(self, client, app):
        """Kurulum betiklerine ve CI adimlarina konabilmesi icin."""
        await admin_olustur("ilkadmin", "ilkadmin@example.com", PAROLA)
        sonuc = await admin_olustur("ilkadmin", "ilkadmin@example.com", PAROLA)

        assert "dokunulmadi" in sonuc

    async def test_var_olan_kullaniciyi_admin_yapiyor(self, client, app):
        """Kendi kaydini acmis birini sonradan yetkilendirme yolu."""
        await register_user(client)

        sonuc = await admin_olustur(
            DEFAULT_USER["username"], DEFAULT_USER["email"], PAROLA
        )

        assert "admin yapildi" in sonuc
        kullanici = await kullaniciyi_getir(app, DEFAULT_USER["username"])
        assert kullanici.is_admin is True

    async def test_var_olan_kullanicinin_parolasi_degismiyor(self, client, app):
        """Yetkilendirme parola sifirlama degil.

        Betik parolayi da ezseydi, bir hesabi admin yapmak o hesaba
        girmenin yolu olurdu.
        """
        await register_user(client)
        await admin_olustur(DEFAULT_USER["username"], DEFAULT_USER["email"], PAROLA)

        # Kullanicinin kendi parolasi hala calisiyor.
        token = await login(client)
        assert token

        # Betige verilen parola ise bir sey acmiyor.
        response = await client.post(
            "/api/v1/auth/token",
            data={"username": DEFAULT_USER["email"], "password": PAROLA},
        )
        assert response.status_code == 401, response.text

    async def test_kullanici_adi_baskasinin_e_postasiyla_eslesirse_duruyor(
        self, client, app
    ):
        """Iki ayri kaydi tek komutla karistirmak yerine anlasilir hata.

        username ve email ayri UNIQUE kisitlar; farkli kayitlara
        dusuyorlarsa INSERT zaten patlardi.
        """
        await register_user(client)

        with pytest.raises(SystemExit):
            await admin_olustur("baskaad", DEFAULT_USER["email"], PAROLA)

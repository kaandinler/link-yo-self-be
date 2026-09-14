"""Auth akisi testleri: kayit, giris, token yenileme, cikis."""
import pytest

from tests.conftest import (
    DEFAULT_USER,
    auth_header,
    login,
    register_user,
    request_reset_token,
)


class TestRegister:
    async def test_kayit_basarili(self, client):
        response = await client.post("/api/v1/auth/register", json=DEFAULT_USER)

        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "success"
        assert body["data"]["username"] == "kaan"
        assert body["data"]["email"] == "kaan@example.com"
        # Sifre hicbir sekilde yanitta donmemeli
        assert "password" not in body["data"]
        assert "hashed_password" not in body["data"]

    async def test_ayni_kullanici_adi_reddedilir(self, client):
        await register_user(client)

        response = await client.post(
            "/api/v1/auth/register",
            json={**DEFAULT_USER, "email": "baska@example.com"},
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["message"]

    async def test_ayni_eposta_reddedilir(self, client):
        await register_user(client)

        response = await client.post(
            "/api/v1/auth/register",
            json={**DEFAULT_USER, "username": "baskakullanici"},
        )

        assert response.status_code == 409

    async def test_kullanici_adi_kucuk_harfe_cevrilir(self, client):
        user = await register_user(client, username="KaanDinler")
        assert user["username"] == "kaandinler"

    @pytest.mark.parametrize(
        "alan,deger",
        [
            ("password", "123"),            # min 6 karakter
            ("username", "ab"),             # min 3 karakter
            ("username", "admin"),          # rezerve kelime
            ("email", "gecersiz-eposta"),   # format hatasi
            ("username", "kaan!!!"),        # gecersiz karakter (bkz. asagidaki not)
        ],
    )
    async def test_gecersiz_kayit_verisi(self, client, alan, deger):
        response = await client.post(
            "/api/v1/auth/register", json={**DEFAULT_USER, alan: deger}
        )
        assert response.status_code == 422


class TestRezerveKullaniciAdlari:
    """Profil sayfasi /{username} adresinde yayinlandigi icin frontend
    rotalariyla cakisan adlar alinamamali; aksi halde o kullanicinin sayfasina
    hicbir zaman ulasilamaz.
    """

    @pytest.mark.parametrize(
        "username",
        ["dashboard", "settings", "links", "sign-in", "profile", "admin-panel"],
    )
    async def test_frontend_rotalari_rezerve(self, client, username):
        response = await client.post(
            "/api/v1/auth/register",
            json={**DEFAULT_USER, "username": username},
        )

        assert response.status_code == 422

    async def test_normal_kullanici_adi_kabul_edilir(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={**DEFAULT_USER, "username": "kaandinler"},
        )

        assert response.status_code == 201


class TestLogin:
    async def test_eposta_ile_giris(self, client):
        await register_user(client)

        response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"

    async def test_kullanici_adi_ile_giris(self, client):
        """OAuth2 form alani 'username' oldugu icin kullanici adi da calismali."""
        await register_user(client)

        response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["username"],
                "password": DEFAULT_USER["password"],
            },
        )

        assert response.status_code == 200
        assert response.json()["data"]["access_token"]

    async def test_yanlis_sifre_401(self, client):
        await register_user(client)

        response = await client.post(
            "/api/v1/auth/token",
            data={"username": DEFAULT_USER["email"], "password": "yanlis-sifre"},
        )

        assert response.status_code == 401

    async def test_olmayan_kullanici_401(self, client):
        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "yok@example.com", "password": "secret123"},
        )

        assert response.status_code == 401


class TestRefreshToken:
    async def test_refresh_yeni_access_token_verir(self, client):
        await register_user(client)
        login_response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        refresh_token = login_response.json()["data"]["refresh_token"]

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        assert response.json()["data"]["access_token"]

    async def test_gecersiz_refresh_token_401(self, client):
        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": "boyle-bir-token-yok"}
        )

        assert response.status_code == 401


class TestLogout:
    async def test_logout_refresh_tokenlari_iptal_eder(self, client):
        await register_user(client)
        login_response = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        data = login_response.json()["data"]

        logout = await client.post(
            "/api/v1/auth/logout", headers=auth_header(data["access_token"])
        )
        assert logout.status_code == 204

        # Iptal edilen refresh token artik kullanilamaz
        refresh = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": data["refresh_token"]}
        )
        assert refresh.status_code == 401

    async def test_tokensiz_logout_401(self, client):
        response = await client.post("/api/v1/auth/logout")
        assert response.status_code == 401


class TestKorumaliEndpointler:
    async def test_tokensiz_erisim_401(self, client):
        response = await client.get("/api/v1/users/me")
        assert response.status_code == 401

    async def test_bozuk_token_401(self, client):
        response = await client.get(
            "/api/v1/users/me", headers=auth_header("bu.gecerli.bir.token.degil")
        )
        assert response.status_code == 401

    async def test_gecerli_token_200(self, client):
        await register_user(client)
        token = await login(client)

        response = await client.get("/api/v1/users/me", headers=auth_header(token))

        assert response.status_code == 200


class TestSifreSifirlama:
    """POST /auth/forgot-password ve /auth/reset-password."""

    async def test_talep_204_doner(self, client):
        await register_user(client)

        response = await client.post(
            "/api/v1/auth/forgot-password", json={"email": DEFAULT_USER["email"]}
        )

        assert response.status_code == 204

    async def test_olmayan_eposta_da_204_doner(self, client):
        """Kullanici numaralandirmayi onlemek icin yanit ayni olmali."""
        response = await client.post(
            "/api/v1/auth/forgot-password", json={"email": "yok@example.com"}
        )

        assert response.status_code == 204

    async def test_token_ile_sifre_degisir(self, client, app):
        await register_user(client)
        token = await request_reset_token(client, app)

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "yenisifre123"},
        )
        assert response.status_code == 204

        # Eski sifre calismamali, yenisi calismali
        eski = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        assert eski.status_code == 401

        yeni = await client.post(
            "/api/v1/auth/token",
            data={"username": DEFAULT_USER["email"], "password": "yenisifre123"},
        )
        assert yeni.status_code == 200

    async def test_token_tek_kullanimlik(self, client, app):
        await register_user(client)
        token = await request_reset_token(client, app)

        ilk = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "yenisifre123"},
        )
        assert ilk.status_code == 204

        ikinci = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "baskasifre123"},
        )
        assert ikinci.status_code == 400

    async def test_gecersiz_token_400(self, client):
        await register_user(client)

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "boyle-bir-token-yok", "password": "yenisifre123"},
        )

        assert response.status_code == 400
        assert response.json()["status"] == "error"

    async def test_yeni_talep_eskisini_gecersiz_kilar(self, client, app):
        await register_user(client)
        eski_token = await request_reset_token(client, app)
        yeni_token = await request_reset_token(client, app)

        assert eski_token != yeni_token

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": eski_token, "password": "yenisifre123"},
        )
        assert response.status_code == 400

    async def test_sifre_degisince_oturumlar_kapanir(self, client, app):
        """Sifre sifirlandiginda diger cihazlardaki refresh token'lar da gecersiz."""
        await register_user(client)
        giris = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        refresh_token = giris.json()["data"]["refresh_token"]

        token = await request_reset_token(client, app)
        await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "yenisifre123"},
        )

        response = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert response.status_code == 401

    async def test_kisa_sifre_422(self, client, app):
        await register_user(client)
        token = await request_reset_token(client, app)

        response = await client.post(
            "/api/v1/auth/reset-password", json={"token": token, "password": "123"}
        )

        assert response.status_code == 422


class TestSifreDegistir:
    """POST /auth/change-password - giris yapmis kullanicinin sifre degisimi."""

    async def test_tokensiz_401(self, client):
        response = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "secret123", "new_password": "yenisifre1"},
        )
        assert response.status_code == 401

    async def test_yanlis_mevcut_sifre_403(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "yanlis", "new_password": "yenisifre1"},
        )

        assert response.status_code == 403
        # Sifre degismemis olmali
        giris = await auth_client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        assert giris.status_code == 200

    async def test_kisa_yeni_sifre_422(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": DEFAULT_USER["password"], "new_password": "abc"},
        )
        assert response.status_code == 422

    async def test_sifre_degisir(self, auth_client, client):
        response = await auth_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": DEFAULT_USER["password"],
                "new_password": "yenisifre1",
            },
        )

        assert response.status_code == 200, response.text

        yeni = await client.post(
            "/api/v1/auth/token",
            data={"username": DEFAULT_USER["email"], "password": "yenisifre1"},
        )
        assert yeni.status_code == 200

        eski = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        assert eski.status_code == 401

    async def test_yeni_token_cifti_doner_ve_calisir(self, auth_client):
        """Kullanici kendi oturumundan atilmamali."""
        response = await auth_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": DEFAULT_USER["password"],
                "new_password": "yenisifre1",
            },
        )

        tokenlar = response.json()["data"]
        assert tokenlar["access_token"]
        assert tokenlar["refresh_token"]

        yenile = await auth_client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokenlar["refresh_token"]}
        )
        assert yenile.status_code == 200

    async def test_diger_oturumlar_kapanir(self, client):
        """Baska bir cihazdaki refresh token gecersizlesmeli."""
        await register_user(client)
        eski_oturum = (
            await client.post(
                "/api/v1/auth/token",
                data={
                    "username": DEFAULT_USER["email"],
                    "password": DEFAULT_USER["password"],
                },
            )
        ).json()["data"]

        token = await login(client)
        await client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": DEFAULT_USER["password"],
                "new_password": "yenisifre1",
            },
            headers=auth_header(token),
        )

        yenile = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": eski_oturum["refresh_token"]},
        )
        assert yenile.status_code == 401


class TestEpostaDegistir:
    """POST /auth/change-email"""

    async def test_tokensiz_401(self, client):
        response = await client.post(
            "/api/v1/auth/change-email",
            json={"password": "secret123", "new_email": "yeni@example.com"},
        )
        assert response.status_code == 401

    async def test_yanlis_sifre_403(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/change-email",
            json={"password": "yanlis", "new_email": "yeni@example.com"},
        )

        assert response.status_code == 403
        assert (
            await auth_client.get("/api/v1/users/me")
        ).json()["data"]["email"] == DEFAULT_USER["email"]

    async def test_gecersiz_eposta_422(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/change-email",
            json={"password": DEFAULT_USER["password"], "new_email": "eposta-degil"},
        )
        assert response.status_code == 422

    async def test_eposta_degisir_ve_yeni_adresle_giris_yapilir(
        self, auth_client, client
    ):
        response = await auth_client.post(
            "/api/v1/auth/change-email",
            json={
                "password": DEFAULT_USER["password"],
                "new_email": "yeni@example.com",
            },
        )

        assert response.status_code == 200, response.text
        assert response.json()["data"]["email"] == "yeni@example.com"

        yeni = await client.post(
            "/api/v1/auth/token",
            data={
                "username": "yeni@example.com",
                "password": DEFAULT_USER["password"],
            },
        )
        assert yeni.status_code == 200

        eski = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        assert eski.status_code == 401

    async def test_buyuk_harfli_adres_kucultulur(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/change-email",
            json={
                "password": DEFAULT_USER["password"],
                "new_email": "Yeni@Example.COM",
            },
        )

        assert response.json()["data"]["email"] == "yeni@example.com"

    async def test_baskasinin_epostasi_409(self, auth_client):
        await register_user(
            auth_client, username="baska", email="baska@example.com"
        )

        response = await auth_client.post(
            "/api/v1/auth/change-email",
            json={
                "password": DEFAULT_USER["password"],
                "new_email": "baska@example.com",
            },
        )

        assert response.status_code == 409

    async def test_ayni_adres_hata_vermez(self, auth_client):
        """Kendi adresini tekrar gondermek catisma sayilmamali."""
        response = await auth_client.post(
            "/api/v1/auth/change-email",
            json={
                "password": DEFAULT_USER["password"],
                "new_email": DEFAULT_USER["email"],
            },
        )

        assert response.status_code == 200, response.text

    async def test_sifre_sifirlama_yeni_adrese_gider(self, auth_client, app):
        """E-posta degistikten sonra sifirlama yeni adres uzerinden calismali."""
        await auth_client.post(
            "/api/v1/auth/change-email",
            json={
                "password": DEFAULT_USER["password"],
                "new_email": "yeni@example.com",
            },
        )

        gonderilen: list[str] = []
        sender = app.container.email_sender()
        orijinal = sender.send
        sender.send = lambda to, subject, body: gonderilen.append(to)
        try:
            response = await auth_client.post(
                "/api/v1/auth/forgot-password", json={"email": "yeni@example.com"}
            )
        finally:
            sender.send = orijinal

        assert response.status_code == 204
        assert gonderilen == ["yeni@example.com"]

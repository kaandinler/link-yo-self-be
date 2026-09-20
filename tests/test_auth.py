"""Auth akisi testleri: kayit, giris, token yenileme, cikis."""

import pytest

from tests.conftest import (
    DEFAULT_USER,
    auth_header,
    login,
    register_user,
    request_reset_token,
    token_cikar,
    yakala_epostalar,
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
            ("password", "123"),  # min 6 karakter
            ("username", "ab"),  # min 3 karakter
            ("username", "admin"),  # rezerve kelime
            ("email", "gecersiz-eposta"),  # format hatasi
            ("username", "kaan!!!"),  # gecersiz karakter (bkz. asagidaki not)
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
            data={"username": "yok@example.com", "password": "Secret123"},
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
            json={"token": token, "password": "YeniSifre123"},
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
            data={"username": DEFAULT_USER["email"], "password": "YeniSifre123"},
        )
        assert yeni.status_code == 200

    async def test_token_tek_kullanimlik(self, client, app):
        await register_user(client)
        token = await request_reset_token(client, app)

        ilk = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "YeniSifre123"},
        )
        assert ilk.status_code == 204

        ikinci = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "password": "BaskaSifre123"},
        )
        assert ikinci.status_code == 400

    async def test_gecersiz_token_400(self, client):
        await register_user(client)

        response = await client.post(
            "/api/v1/auth/reset-password",
            json={"token": "boyle-bir-token-yok", "password": "YeniSifre123"},
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
            json={"token": eski_token, "password": "YeniSifre123"},
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
            json={"token": token, "password": "YeniSifre123"},
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
            json={"current_password": "Secret123", "new_password": "YeniSifre1"},
        )
        assert response.status_code == 401

    async def test_yanlis_mevcut_sifre_403(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "yanlis", "new_password": "YeniSifre1"},
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
                "new_password": "YeniSifre1",
            },
        )

        assert response.status_code == 200, response.text

        yeni = await client.post(
            "/api/v1/auth/token",
            data={"username": DEFAULT_USER["email"], "password": "YeniSifre1"},
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
                "new_password": "YeniSifre1",
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
                "new_password": "YeniSifre1",
            },
            headers=auth_header(token),
        )

        yenile = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": eski_oturum["refresh_token"]},
        )
        assert yenile.status_code == 401


class TestEpostaDegistirTalebi:
    """POST /auth/change-email - adres BURADA degismiyor, talep aciliyor."""

    async def test_tokensiz_401(self, client):
        response = await client.post(
            "/api/v1/auth/change-email",
            json={"password": "Secret123", "new_email": "yeni@example.com"},
        )
        assert response.status_code == 401

    async def test_yanlis_sifre_403(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/change-email",
            json={"password": "yanlis", "new_email": "yeni@example.com"},
        )

        assert response.status_code == 403
        assert (await auth_client.get("/api/v1/users/me")).json()["data"][
            "email"
        ] == DEFAULT_USER["email"]

    async def test_gecersiz_eposta_422(self, auth_client):
        response = await auth_client.post(
            "/api/v1/auth/change-email",
            json={"password": DEFAULT_USER["password"], "new_email": "eposta-degil"},
        )
        assert response.status_code == 422

    async def test_talep_adresi_hemen_degistirmez(self, auth_client, app, client):
        """Regresyon: onceki hali adresi dogrudan yaziyordu.

        Yanlis yazilan bir adres kullaniciyi sifre sifirlamadan -- tek kurtarma
        yolundan -- ederdi.
        """
        with yakala_epostalar(app) as gonderilen:
            response = await auth_client.post(
                "/api/v1/auth/change-email",
                json={
                    "password": DEFAULT_USER["password"],
                    "new_email": "yeni@example.com",
                },
            )

        assert response.status_code == 202, response.text
        assert response.json()["data"]["pending_email"] == "yeni@example.com"

        # Adres hala eski
        me = (await auth_client.get("/api/v1/users/me")).json()["data"]
        assert me["email"] == DEFAULT_USER["email"]

        # Eski adresle giris calismaya devam ediyor
        eski = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        assert eski.status_code == 200

        # Baglanti YENI adrese gitti
        assert gonderilen[-1]["to"] == "yeni@example.com"

    async def test_buyuk_harfli_adres_kucultulur(self, auth_client, app):
        with yakala_epostalar(app) as gonderilen:
            response = await auth_client.post(
                "/api/v1/auth/change-email",
                json={
                    "password": DEFAULT_USER["password"],
                    "new_email": "Yeni@Example.COM",
                },
            )

        assert response.json()["data"]["pending_email"] == "yeni@example.com"
        assert gonderilen[-1]["to"] == "yeni@example.com"

    async def test_baskasinin_epostasi_409(self, auth_client):
        await register_user(auth_client, username="baska", email="baska@example.com")

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

        assert response.status_code == 202, response.text


class TestEpostaDogrulama:
    """POST /auth/verify-email ve /auth/resend-verification"""

    async def test_kayit_dogrulama_maili_gonderir(self, client, app):
        with yakala_epostalar(app) as gonderilen:
            await register_user(client)

        assert gonderilen, "dogrulama e-postasi gonderilmedi"
        assert gonderilen[-1]["to"] == DEFAULT_USER["email"]
        assert "confirm-email?token=" in gonderilen[-1]["body"]

    async def test_yeni_kullanici_dogrulanmamis(self, auth_client):
        me = (await auth_client.get("/api/v1/users/me")).json()["data"]
        assert me["email_verified"] is False

    async def test_baglanti_adresi_dogrular(self, client, app):
        with yakala_epostalar(app) as gonderilen:
            await register_user(client)
        token = token_cikar(gonderilen[-1]["body"])

        response = await client.post("/api/v1/auth/verify-email", json={"token": token})

        assert response.status_code == 200, response.text
        assert response.json()["data"]["email_verified"] is True

    async def test_uc_token_istemez(self, client, app):
        """Kullanici baglantiya baska bir cihazdan tiklamis olabilir."""
        with yakala_epostalar(app) as gonderilen:
            await register_user(client)
        token = token_cikar(gonderilen[-1]["body"])

        # Authorization basligi olmadan
        response = await client.post("/api/v1/auth/verify-email", json={"token": token})
        assert response.status_code == 200

    async def test_gecersiz_token_400(self, client):
        response = await client.post(
            "/api/v1/auth/verify-email", json={"token": "uydurma-token"}
        )
        assert response.status_code == 400

    async def test_token_tek_kullanimlik(self, client, app):
        with yakala_epostalar(app) as gonderilen:
            await register_user(client)
        token = token_cikar(gonderilen[-1]["body"])

        await client.post("/api/v1/auth/verify-email", json={"token": token})
        ikinci = await client.post("/api/v1/auth/verify-email", json={"token": token})

        assert ikinci.status_code == 400

    async def test_onay_adresi_degistirir(self, auth_client, app, client):
        """Adres degisikligi ancak baglantiya tiklandiginda uygulaniyor."""
        with yakala_epostalar(app) as gonderilen:
            await auth_client.post(
                "/api/v1/auth/change-email",
                json={
                    "password": DEFAULT_USER["password"],
                    "new_email": "yeni@example.com",
                },
            )
        token = token_cikar(gonderilen[-1]["body"])

        response = await client.post("/api/v1/auth/verify-email", json={"token": token})

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["email"] == "yeni@example.com"
        assert data["email_verified"] is True

        yeni_giris = await client.post(
            "/api/v1/auth/token",
            data={
                "username": "yeni@example.com",
                "password": DEFAULT_USER["password"],
            },
        )
        assert yeni_giris.status_code == 200

        eski_giris = await client.post(
            "/api/v1/auth/token",
            data={
                "username": DEFAULT_USER["email"],
                "password": DEFAULT_USER["password"],
            },
        )
        assert eski_giris.status_code == 401

    async def test_arada_kapilan_adres_409(self, auth_client, app, client):
        """Talep ile onay arasinda adresi baskasi almis olabilir."""
        with yakala_epostalar(app) as gonderilen:
            await auth_client.post(
                "/api/v1/auth/change-email",
                json={
                    "password": DEFAULT_USER["password"],
                    "new_email": "yeni@example.com",
                },
            )
        token = token_cikar(gonderilen[-1]["body"])

        await register_user(auth_client, username="rakip", email="yeni@example.com")

        response = await client.post("/api/v1/auth/verify-email", json={"token": token})

        assert response.status_code == 409

    async def test_yeni_talep_eskisini_gecersiz_kilar(self, auth_client, app, client):
        """Vazgecilen bir adrese ait eski baglanti sonradan gecis yapmamali."""
        with yakala_epostalar(app) as gonderilen:
            await auth_client.post(
                "/api/v1/auth/change-email",
                json={
                    "password": DEFAULT_USER["password"],
                    "new_email": "ilk@example.com",
                },
            )
            ilk_token = token_cikar(gonderilen[-1]["body"])

            await auth_client.post(
                "/api/v1/auth/change-email",
                json={
                    "password": DEFAULT_USER["password"],
                    "new_email": "ikinci@example.com",
                },
            )
            ikinci_token = token_cikar(gonderilen[-1]["body"])

        eski = await client.post("/api/v1/auth/verify-email", json={"token": ilk_token})
        assert eski.status_code == 400

        yeni = await client.post(
            "/api/v1/auth/verify-email", json={"token": ikinci_token}
        )
        assert yeni.json()["data"]["email"] == "ikinci@example.com"

    async def test_yeniden_gonder_mevcut_adrese(self, auth_client, app):
        with yakala_epostalar(app) as gonderilen:
            response = await auth_client.post("/api/v1/auth/resend-verification")

        assert response.status_code == 200, response.text
        assert response.json()["data"]["pending_email"] == DEFAULT_USER["email"]
        assert gonderilen[-1]["to"] == DEFAULT_USER["email"]

    async def test_yeniden_gonder_bekleyen_adrese(self, auth_client, app):
        """Onay bekleyen bir degisiklik varsa baglanti yine o adrese gitmeli."""
        await auth_client.post(
            "/api/v1/auth/change-email",
            json={
                "password": DEFAULT_USER["password"],
                "new_email": "yeni@example.com",
            },
        )

        with yakala_epostalar(app) as gonderilen:
            response = await auth_client.post("/api/v1/auth/resend-verification")

        assert response.json()["data"]["pending_email"] == "yeni@example.com"
        assert gonderilen[-1]["to"] == "yeni@example.com"

    async def test_yeniden_gonder_tokensiz_401(self, client):
        response = await client.post("/api/v1/auth/resend-verification")
        assert response.status_code == 401

    async def test_silinen_kullanici_dogrulanamaz(self, auth_client, app, client):
        with yakala_epostalar(app) as gonderilen:
            response = await auth_client.post("/api/v1/auth/resend-verification")
            assert response.status_code == 200
        token = token_cikar(gonderilen[-1]["body"])

        await auth_client.request(
            "DELETE", "/api/v1/users/me", json={"password": DEFAULT_USER["password"]}
        )

        response = await client.post("/api/v1/auth/verify-email", json={"token": token})
        assert response.status_code == 400


# (aciklama, kurala uymayan sifre)
GECERSIZ_SIFRELER = [
    ("kisa", "Abc123"),
    ("buyuk harf yok", "secret123"),
    ("kucuk harf yok", "SECRET123"),
    ("rakam yok", "SecretPass"),
]


class TestSifreKurali:
    """Sifre kurali TEK kaynaktan (core.validators) gelmeli.

    ONCEDEN AYRISMISTI: her DTO kendi min_length=6 degerini tasiyordu, kayit
    formu ise 8 karakter + buyuk/kucuk harf + rakam istiyordu. Kullanici
    formda reddedilen bir sifreyi baska bir uctan sorunsuz belirleyebiliyordu.
    """

    @pytest.mark.parametrize("aciklama,sifre", GECERSIZ_SIFRELER)
    async def test_kayit_reddeder(self, client, aciklama, sifre):
        response = await client.post(
            "/api/v1/auth/register",
            json={"username": "yeni", "email": "yeni@example.com", "password": sifre},
        )
        assert response.status_code == 422, aciklama

    @pytest.mark.parametrize("aciklama,sifre", GECERSIZ_SIFRELER)
    async def test_sifre_degistirme_reddeder(self, auth_client, aciklama, sifre):
        response = await auth_client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": DEFAULT_USER["password"],
                "new_password": sifre,
            },
        )
        assert response.status_code == 422, aciklama

    @pytest.mark.parametrize("aciklama,sifre", GECERSIZ_SIFRELER)
    async def test_sifre_sifirlama_reddeder(self, client, app, aciklama, sifre):
        await register_user(client)
        token = await request_reset_token(client, app)

        response = await client.post(
            "/api/v1/auth/reset-password", json={"token": token, "password": sifre}
        )
        assert response.status_code == 422, aciklama

    @pytest.mark.parametrize("aciklama,sifre", GECERSIZ_SIFRELER)
    async def test_admin_olusturma_reddeder(self, admin_client, aciklama, sifre):
        response = await admin_client.post(
            "/api/v1/users/",
            json={"username": "yeni", "email": "yeni@example.com", "password": sifre},
        )
        assert response.status_code == 422, aciklama

    @pytest.mark.parametrize("aciklama,sifre", GECERSIZ_SIFRELER)
    async def test_admin_guncelleme_reddeder(self, admin_client, aciklama, sifre):
        me = (await admin_client.get("/api/v1/users/me")).json()["data"]

        response = await admin_client.patch(
            f"/api/v1/users/{me['id']}", json={"password": sifre}
        )
        assert response.status_code == 422, aciklama

    async def test_uzun_sifre_reddeder(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "yeni",
                "email": "yeni@example.com",
                "password": "Aa1" + "x" * 60,
            },
        )
        assert response.status_code == 422

    async def test_gecerli_sifre_kabul_edilir(self, client):
        response = await client.post(
            "/api/v1/auth/register",
            json={
                "username": "yeni",
                "email": "yeni@example.com",
                "password": "Gecerli1",
            },
        )
        assert response.status_code == 201, response.text

    async def test_eski_kullanicilar_giris_yapabilir(self, client, app):
        """Kural sikilastiginda mevcut kullanicilar disarida kalmamali.

        Giris sirasinda sifre yeniden dogrulanmiyor; yalnizca YENI sifreler
        kuraldan geciyor.
        """
        from sqlalchemy import insert

        from core.auth.password import hash_password
        from models import User

        session_factory = app.container.async_session_factory()
        async with session_factory() as session:
            await session.execute(
                insert(User).values(
                    username="eski",
                    email="eski@example.com",
                    # Yeni kurala uymayan, migration oncesinden kalma sifre
                    hashed_password=hash_password("zayif"),
                    is_deleted=False,
                    profile_completed=False,
                    onboarding_completed=False,
                    is_admin=False,
                    profile_view_count=0,
                    email_verified=False,
                )
            )
            await session.commit()

        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "eski@example.com", "password": "zayif"},
        )
        assert response.status_code == 200

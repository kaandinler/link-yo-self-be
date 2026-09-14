"""Kullanici endpoint'leri: /users/me, /users/{id}, /users/ (admin)."""
from tests.conftest import DEFAULT_USER, auth_header, login, make_admin, register_user


class TestUsersMe:
    async def test_me_kendi_profilini_doner(self, auth_client):
        """Regresyon: /me route'u /{user_id}'den once tanimli olmali, yoksa 422."""
        response = await auth_client.get("/api/v1/users/me")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["username"] == DEFAULT_USER["username"]
        assert data["email"] == DEFAULT_USER["email"]

    async def test_me_int_olarak_parse_edilmez(self, auth_client):
        """'me' path parametresi olarak yorumlanip 422 vermemeli."""
        response = await auth_client.get("/api/v1/users/me")
        assert response.status_code != 422

    async def test_me_profil_tamamlanma_yuzdesi_doner(self, auth_client):
        response = await auth_client.get("/api/v1/users/me")

        assert response.json()["data"]["profile_completion_percentage"] == 0


class TestGetUser:
    async def test_id_ile_kullanici_getir(self, auth_client):
        me = (await auth_client.get("/api/v1/users/me")).json()["data"]

        response = await auth_client.get(f"/api/v1/users/{me['id']}")

        assert response.status_code == 200
        assert response.json()["data"]["id"] == me["id"]

    async def test_olmayan_kullanici_404(self, auth_client):
        response = await auth_client.get("/api/v1/users/99999")

        assert response.status_code == 404
        assert response.json()["status"] == "error"

    async def test_tokensiz_401(self, client):
        response = await client.get("/api/v1/users/1")
        assert response.status_code == 401


class TestListUsers:
    async def test_normal_kullanici_403(self, auth_client):
        response = await auth_client.get("/api/v1/users/")
        assert response.status_code == 403

    async def test_admin_kullanici_listeyi_gorur(self, client, app):
        """Regresyon: admin kontrolu is_admin alanina bagli olmali.

        Onceden `username == "admin"` sarti vardi ve "admin" kayit sirasinda
        rezerve kelime oldugu icin bu endpoint'e hic erisilemiyordu.
        """
        await register_user(client)
        await make_admin(app, DEFAULT_USER["username"])
        token = await login(client)

        response = await client.get("/api/v1/users/", headers=auth_header(token))

        assert response.status_code == 200
        assert len(response.json()["data"]) == 1


class TestAdminBayragi:
    async def test_is_admin_yanitta_doner(self, auth_client):
        """Frontend admin sayfalarini gizleyebilmek icin bu alani okuyor."""
        response = await auth_client.get("/api/v1/users/me")

        assert response.status_code == 200
        assert response.json()["data"]["is_admin"] is False

    async def test_admin_kullanicida_true(self, client, app):
        await register_user(client)
        await make_admin(app, DEFAULT_USER["username"])
        token = await login(client)

        response = await client.get("/api/v1/users/me", headers=auth_header(token))

        assert response.json()["data"]["is_admin"] is True


class TestAdminKullaniciOlustur:
    """POST /users/ - admin panelinden kullanici olusturma."""

    async def test_normal_kullanici_403(self, auth_client):
        response = await auth_client.post(
            "/api/v1/users/",
            json={"username": "yeni", "email": "yeni@example.com", "password": "secret123"},
        )
        assert response.status_code == 403

    async def test_tokensiz_401(self, client):
        response = await client.post(
            "/api/v1/users/",
            json={"username": "yeni", "email": "yeni@example.com", "password": "secret123"},
        )
        assert response.status_code == 401

    async def test_admin_kullanici_olusturur(self, admin_client):
        response = await admin_client.post(
            "/api/v1/users/",
            json={
                "username": "yeni",
                "email": "yeni@example.com",
                "password": "secret123",
                "first_name": "Yeni",
                "last_name": "Kullanici",
            },
        )

        assert response.status_code == 201, response.text
        data = response.json()["data"]
        assert data["username"] == "yeni"
        assert data["first_name"] == "Yeni"
        # is_admin gonderilmediyse varsayilan False olmali.
        assert data["is_admin"] is False
        # Sifre hicbir sekilde yanitta yer almamali.
        assert "password" not in data
        assert "hashed_password" not in data

    async def test_olusturulan_kullanici_giris_yapabilir(self, admin_client):
        await admin_client.post(
            "/api/v1/users/",
            json={"username": "yeni", "email": "yeni@example.com", "password": "secret123"},
        )

        token = await login(admin_client, "yeni@example.com", "secret123")
        assert token

    async def test_admin_olarak_olusturulabilir(self, admin_client):
        response = await admin_client.post(
            "/api/v1/users/",
            json={
                "username": "patron",
                "email": "patron@example.com",
                "password": "secret123",
                "is_admin": True,
            },
        )

        assert response.json()["data"]["is_admin"] is True

    async def test_mukerrer_kullanici_adi_409(self, admin_client):
        response = await admin_client.post(
            "/api/v1/users/",
            json={
                "username": DEFAULT_USER["username"],
                "email": "baska@example.com",
                "password": "secret123",
            },
        )
        assert response.status_code == 409

    async def test_mukerrer_eposta_409(self, admin_client):
        response = await admin_client.post(
            "/api/v1/users/",
            json={
                "username": "baska",
                "email": DEFAULT_USER["email"],
                "password": "secret123",
            },
        )
        assert response.status_code == 409

    async def test_rezerve_kullanici_adi_422(self, admin_client):
        """Rezerve adlar admin uzerinden de alinamamali; /dashboard gibi bir
        frontend rotasiyla cakisirsa o profil sayfasina hic ulasilamaz."""
        response = await admin_client.post(
            "/api/v1/users/",
            json={"username": "dashboard", "email": "d@example.com", "password": "secret123"},
        )
        assert response.status_code == 422


class TestAdminKullaniciGuncelle:
    """PATCH /users/{id}"""

    async def test_normal_kullanici_403(self, auth_client):
        me = (await auth_client.get("/api/v1/users/me")).json()["data"]
        response = await auth_client.patch(
            f"/api/v1/users/{me['id']}", json={"first_name": "X"}
        )
        assert response.status_code == 403

    async def test_kismi_guncelleme_diger_alanlari_bozmaz(self, admin_client):
        hedef = (
            await admin_client.post(
                "/api/v1/users/",
                json={
                    "username": "hedef",
                    "email": "hedef@example.com",
                    "password": "secret123",
                    "last_name": "Soyad",
                },
            )
        ).json()["data"]

        response = await admin_client.patch(
            f"/api/v1/users/{hedef['id']}", json={"first_name": "Ad"}
        )

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["first_name"] == "Ad"
        assert data["last_name"] == "Soyad"
        assert data["email"] == "hedef@example.com"

    async def test_sifre_degistirilince_yeni_sifreyle_girilir(self, admin_client, client):
        hedef = (
            await admin_client.post(
                "/api/v1/users/",
                json={"username": "hedef", "email": "hedef@example.com", "password": "secret123"},
            )
        ).json()["data"]

        await admin_client.patch(
            f"/api/v1/users/{hedef['id']}", json={"password": "yenisifre1"}
        )

        token = await login(client, "hedef@example.com", "yenisifre1")
        assert token

        eski = await client.post(
            "/api/v1/auth/token",
            data={"username": "hedef@example.com", "password": "secret123"},
        )
        assert eski.status_code == 401

    async def test_admin_yetkisi_verilebilir(self, admin_client):
        hedef = (
            await admin_client.post(
                "/api/v1/users/",
                json={"username": "hedef", "email": "hedef@example.com", "password": "secret123"},
            )
        ).json()["data"]

        response = await admin_client.patch(
            f"/api/v1/users/{hedef['id']}", json={"is_admin": True}
        )

        assert response.json()["data"]["is_admin"] is True

    async def test_admin_kendi_yetkisini_alamaz(self, admin_client):
        """Son admin kendini yetkisizlestirirse panele bir daha girilemez."""
        me = (await admin_client.get("/api/v1/users/me")).json()["data"]

        response = await admin_client.patch(
            f"/api/v1/users/{me['id']}", json={"is_admin": False}
        )

        assert response.status_code == 422
        kontrol = await admin_client.get("/api/v1/users/me")
        assert kontrol.json()["data"]["is_admin"] is True

    async def test_mukerrer_kullanici_adina_cevrilemez(self, admin_client):
        hedef = (
            await admin_client.post(
                "/api/v1/users/",
                json={"username": "hedef", "email": "hedef@example.com", "password": "secret123"},
            )
        ).json()["data"]

        response = await admin_client.patch(
            f"/api/v1/users/{hedef['id']}", json={"username": DEFAULT_USER["username"]}
        )

        assert response.status_code == 409

    async def test_kendi_kullanici_adiyla_guncelleme_catismaz(self, admin_client):
        """Ayni degeri tekrar gondermek 409 vermemeli."""
        me = (await admin_client.get("/api/v1/users/me")).json()["data"]

        response = await admin_client.patch(
            f"/api/v1/users/{me['id']}",
            json={"username": me["username"], "first_name": "Ad"},
        )

        assert response.status_code == 200, response.text

    async def test_olmayan_kullanici_404(self, admin_client):
        response = await admin_client.patch("/api/v1/users/99999", json={"first_name": "X"})
        assert response.status_code == 404


class TestAdminKullaniciSil:
    """DELETE /users/{id} - soft delete."""

    async def test_normal_kullanici_403(self, auth_client):
        me = (await auth_client.get("/api/v1/users/me")).json()["data"]
        response = await auth_client.delete(f"/api/v1/users/{me['id']}")
        assert response.status_code == 403

    async def test_silinen_kullanici_204_ve_listede_yok(self, admin_client):
        hedef = (
            await admin_client.post(
                "/api/v1/users/",
                json={"username": "hedef", "email": "hedef@example.com", "password": "secret123"},
            )
        ).json()["data"]

        response = await admin_client.delete(f"/api/v1/users/{hedef['id']}")
        assert response.status_code == 204

        assert (await admin_client.get(f"/api/v1/users/{hedef['id']}")).status_code == 404

        liste = (await admin_client.get("/api/v1/users/")).json()
        assert all(u["id"] != hedef["id"] for u in liste["data"])

    async def test_silinen_kullanici_giris_yapamaz(self, admin_client, client):
        """Regresyon: is_deleted hicbir sorguda filtrelenmiyordu, silinen
        kullanici normal sekilde giris yapmaya devam ediyordu."""
        hedef = (
            await admin_client.post(
                "/api/v1/users/",
                json={"username": "hedef", "email": "hedef@example.com", "password": "secret123"},
            )
        ).json()["data"]

        await admin_client.delete(f"/api/v1/users/{hedef['id']}")

        response = await client.post(
            "/api/v1/auth/token",
            data={"username": "hedef@example.com", "password": "secret123"},
        )
        assert response.status_code == 401

    async def test_silinen_kullanicinin_token_lari_gecersiz(self, admin_client, client):
        """Elindeki access/refresh token ile API'yi kullanmaya devam edememeli."""
        await admin_client.post(
            "/api/v1/users/",
            json={"username": "hedef", "email": "hedef@example.com", "password": "secret123"},
        )
        giris = await client.post(
            "/api/v1/auth/token",
            data={"username": "hedef@example.com", "password": "secret123"},
        )
        tokenlar = giris.json()["data"]

        hedef = (
            await client.get("/api/v1/users/me", headers=auth_header(tokenlar["access_token"]))
        ).json()["data"]

        await admin_client.delete(f"/api/v1/users/{hedef['id']}")

        # Access token imzasi hala gecerli ama kullanici bulunamamali.
        me = await client.get(
            "/api/v1/users/me", headers=auth_header(tokenlar["access_token"])
        )
        assert me.status_code == 401

        yenile = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": tokenlar["refresh_token"]}
        )
        assert yenile.status_code == 401

    async def test_silinen_kullanicinin_public_profili_404(self, admin_client, client):
        await admin_client.post(
            "/api/v1/users/",
            json={"username": "hedef", "email": "hedef@example.com", "password": "secret123"},
        )
        hedef = (await admin_client.get("/api/v1/users/")).json()["data"]
        hedef_id = next(u["id"] for u in hedef if u["username"] == "hedef")

        await admin_client.delete(f"/api/v1/users/{hedef_id}")

        response = await client.get("/api/v1/p/hedef")
        assert response.status_code == 404

    async def test_admin_kendini_silemez(self, admin_client):
        me = (await admin_client.get("/api/v1/users/me")).json()["data"]

        response = await admin_client.delete(f"/api/v1/users/{me['id']}")

        assert response.status_code == 422
        assert (await admin_client.get("/api/v1/users/me")).status_code == 200

    async def test_olmayan_kullanici_404(self, admin_client):
        response = await admin_client.delete("/api/v1/users/99999")
        assert response.status_code == 404

    async def test_silinen_kullanici_adi_yeniden_alinamaz(self, admin_client, client):
        """Satir tabloda kaldigi ve username UNIQUE oldugu icin kayit 409
        vermeli; 500 (unique ihlali) degil."""
        hedef = (
            await admin_client.post(
                "/api/v1/users/",
                json={"username": "hedef", "email": "hedef@example.com", "password": "secret123"},
            )
        ).json()["data"]
        await admin_client.delete(f"/api/v1/users/{hedef['id']}")

        response = await client.post(
            "/api/v1/auth/register",
            json={"username": "hedef", "email": "yeni@example.com", "password": "secret123"},
        )
        assert response.status_code == 409


class TestKullaniciListesiSayfalama:
    """GET /users/ - sayfalama, arama, siralama."""

    async def _kullanicilar_olustur(self, admin_client, adet: int) -> None:
        for i in range(adet):
            response = await admin_client.post(
                "/api/v1/users/",
                json={
                    "username": f"user{i}",
                    "email": f"user{i}@example.com",
                    "password": "secret123",
                },
            )
            assert response.status_code == 201, response.text

    async def test_meta_toplam_ve_sonraki_sayfa(self, admin_client):
        await self._kullanicilar_olustur(admin_client, 4)  # + admin = 5

        response = await admin_client.get("/api/v1/users/?page=1&limit=2")

        assert response.status_code == 200
        govde = response.json()
        assert len(govde["data"]) == 2
        assert govde["meta"]["total"] == 5
        assert govde["meta"]["total_pages"] == 3
        assert govde["meta"]["has_next_page"] is True

    async def test_son_sayfada_sonraki_yok(self, admin_client):
        await self._kullanicilar_olustur(admin_client, 4)

        response = await admin_client.get("/api/v1/users/?page=3&limit=2")

        govde = response.json()
        assert len(govde["data"]) == 1
        assert govde["meta"]["has_next_page"] is False

    async def test_arama_kullanici_adinda(self, admin_client):
        await self._kullanicilar_olustur(admin_client, 3)

        response = await admin_client.get("/api/v1/users/?search=user1")

        data = response.json()["data"]
        assert len(data) == 1
        assert data[0]["username"] == "user1"

    async def test_arama_epostada(self, admin_client):
        await self._kullanicilar_olustur(admin_client, 2)

        response = await admin_client.get("/api/v1/users/?search=USER0@EXAMPLE")

        assert len(response.json()["data"]) == 1

    async def test_is_admin_filtresi(self, admin_client):
        await self._kullanicilar_olustur(admin_client, 3)

        sadece_admin = await admin_client.get("/api/v1/users/?is_admin=true")
        assert len(sadece_admin.json()["data"]) == 1

        normaller = await admin_client.get("/api/v1/users/?is_admin=false")
        assert len(normaller.json()["data"]) == 3

    async def test_kullanici_adina_gore_siralama(self, admin_client):
        await self._kullanicilar_olustur(admin_client, 3)

        response = await admin_client.get("/api/v1/users/?order_by=username&order=asc")

        adlar = [u["username"] for u in response.json()["data"]]
        assert adlar == sorted(adlar)

    async def test_bilinmeyen_siralama_alani_500_vermez(self, admin_client):
        """Kolon adi istemciden geliyor; beyaz liste disi deger varsayilana
        dusmeli, getattr ile patlamamali."""
        response = await admin_client.get("/api/v1/users/?order_by=hashed_password")

        assert response.status_code == 200

    async def test_limit_ustu_422(self, admin_client):
        response = await admin_client.get("/api/v1/users/?limit=1000")
        assert response.status_code == 422

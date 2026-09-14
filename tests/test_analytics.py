"""GET /analytics/summary - pano ve analytics sayfasinin okudugu ozet."""
from tests.conftest import DEFAULT_USER, auth_header, login, register_user
from tests.test_links import create_link


class TestAnalyticsOzeti:
    async def test_tokensiz_401(self, client):
        response = await client.get("/api/v1/analytics/summary")
        assert response.status_code == 401

    async def test_bos_hesapta_sifirlar(self, auth_client):
        response = await auth_client.get("/api/v1/analytics/summary")

        assert response.status_code == 200, response.text
        data = response.json()["data"]
        assert data["total_links"] == 0
        assert data["active_links"] == 0
        assert data["total_clicks"] == 0
        assert data["profile_view_count"] == 0
        assert data["links"] == []

    async def test_toplamlar_ve_siralama(self, auth_client):
        bir = await create_link(auth_client, title="Bir")
        iki = await create_link(auth_client, title="Iki")
        await auth_client.patch(f"/api/v1/links/{iki['id']}/toggle")
        await auth_client.post(f"/api/v1/links/{bir['id']}/click")
        await auth_client.post(f"/api/v1/links/{bir['id']}/click")

        response = await auth_client.get("/api/v1/analytics/summary")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_links"] == 2
        assert data["active_links"] == 1
        # Pasif linkin gecmis tiklamalari toplamdan dusmemeli.
        assert data["total_clicks"] == 2
        # En cok tiklanan basta
        assert data["links"][0]["title"] == "Bir"

    async def test_profil_bilgileri_doner(self, auth_client):
        data = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]

        assert data["username"] == DEFAULT_USER["username"]
        assert data["profile_url_path"] == f"/{DEFAULT_USER['username']}"

    async def test_baska_kullanicinin_linkleri_sayilmaz(self, auth_client):
        await create_link(auth_client, title="Benim")

        await register_user(
            auth_client, username="baska", email="baska@example.com"
        )
        baska_token = await login(auth_client, "baska@example.com")

        response = await auth_client.get(
            "/api/v1/analytics/summary", headers=auth_header(baska_token)
        )

        assert response.json()["data"]["total_links"] == 0


class TestProfilGoruntulenme:
    async def test_public_profil_ziyareti_sayaci_artirir(self, auth_client):
        await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")
        await auth_client.get(f"/api/v1/p/{DEFAULT_USER['username']}")

        data = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]

        assert data["profile_view_count"] == 2

    async def test_olmayan_profil_sayaci_artirmaz(self, auth_client):
        response = await auth_client.get("/api/v1/p/olmayan")
        assert response.status_code == 404

        data = (await auth_client.get("/api/v1/analytics/summary")).json()["data"]
        assert data["profile_view_count"] == 0

    async def test_sayac_kullaniciya_ozel(self, client):
        await register_user(client)
        await register_user(client, username="baska", email="baska@example.com")
        token = await login(client)
        baska_token = await login(client, "baska@example.com")

        await client.get(f"/api/v1/p/{DEFAULT_USER['username']}")

        benim = (
            await client.get(
                "/api/v1/analytics/summary", headers=auth_header(token)
            )
        ).json()["data"]
        baska = (
            await client.get(
                "/api/v1/analytics/summary", headers=auth_header(baska_token)
            )
        ).json()["data"]

        assert benim["profile_view_count"] == 1
        assert baska["profile_view_count"] == 0

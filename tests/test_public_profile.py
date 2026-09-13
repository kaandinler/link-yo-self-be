"""Public profil sayfasi testleri (token gerektirmez)."""
from tests.conftest import DEFAULT_USER, auth_header, login, register_user

PROFILE_URL = f"/api/v1/p/{DEFAULT_USER['username']}"


class TestPublicProfile:
    async def test_token_gerektirmez(self, client):
        await register_user(client)

        response = await client.get(PROFILE_URL)

        assert response.status_code == 200
        assert response.json()["data"]["username"] == DEFAULT_USER["username"]

    async def test_olmayan_kullanici_404(self, client):
        response = await client.get("/api/v1/p/boyle-biri-yok")

        assert response.status_code == 404
        assert response.json()["status"] == "error"

    async def test_kullanici_adi_buyuk_kucuk_harf_duyarsiz(self, client):
        await register_user(client)

        response = await client.get(f"/api/v1/p/{DEFAULT_USER['username'].upper()}")

        assert response.status_code == 200

    async def test_hassas_alanlar_sizmaz(self, client):
        await register_user(client)

        data = (await client.get(PROFILE_URL)).json()["data"]

        for alan in ("email", "hashed_password", "id", "is_admin",
                     "onboarding_completed", "profile_completed"):
            assert alan not in data, f"{alan} public yanitta olmamali"

    async def test_display_name_yoksa_kullanici_adina_duser(self, client):
        await register_user(client)

        data = (await client.get(PROFILE_URL)).json()["data"]

        assert data["display_name"] == DEFAULT_USER["username"]

    async def test_profil_alanlari_yansir(self, client):
        await register_user(client)
        token = await login(client)
        await client.put(
            "/api/v1/profile/update",
            headers=auth_header(token),
            json={
                "display_name": "Kaan Dinler",
                "bio": "FastAPI & Flutter",
                "page_title": "Kaan'in Linkleri",
                "theme_color": "#FF5733",
                "twitter_username": "kaandinler",
            },
        )

        data = (await client.get(PROFILE_URL)).json()["data"]

        assert data["display_name"] == "Kaan Dinler"
        assert data["bio"] == "FastAPI & Flutter"
        assert data["page_title"] == "Kaan'in Linkleri"
        assert data["theme_color"] == "#FF5733"
        assert data["twitter_username"] == "kaandinler"


class TestPublicProfileLinks:
    async def test_linkler_order_index_sirasiyla_doner(self, client):
        await register_user(client)
        token = await login(client)
        for title in ("Bir", "Iki", "Uc"):
            await client.post(
                "/api/v1/links/",
                headers=auth_header(token),
                json={"title": title, "url": f"https://ornek.com/{title}"},
            )

        data = (await client.get(PROFILE_URL)).json()["data"]

        assert [link["title"] for link in data["links"]] == ["Bir", "Iki", "Uc"]

    async def test_pasif_linkler_gorunmez(self, client):
        await register_user(client)
        token = await login(client)
        link = (
            await client.post(
                "/api/v1/links/",
                headers=auth_header(token),
                json={"title": "Gizli", "url": "https://ornek.com"},
            )
        ).json()["data"]
        await client.patch(
            f"/api/v1/links/{link['id']}/toggle", headers=auth_header(token)
        )

        data = (await client.get(PROFILE_URL)).json()["data"]

        assert data["links"] == []

    async def test_silinen_link_gorunmez(self, client):
        await register_user(client)
        token = await login(client)
        link = (
            await client.post(
                "/api/v1/links/",
                headers=auth_header(token),
                json={"title": "Silinecek", "url": "https://ornek.com"},
            )
        ).json()["data"]
        await client.delete(f"/api/v1/links/{link['id']}", headers=auth_header(token))

        data = (await client.get(PROFILE_URL)).json()["data"]

        assert data["links"] == []

    async def test_click_count_public_yanitta_yok(self, client):
        await register_user(client)
        token = await login(client)
        await client.post(
            "/api/v1/links/",
            headers=auth_header(token),
            json={"title": "Bir", "url": "https://ornek.com"},
        )

        data = (await client.get(PROFILE_URL)).json()["data"]

        assert "click_count" not in data["links"][0]

    async def test_baska_kullanicinin_linkleri_karismaz(self, client):
        await register_user(client)
        sahip_token = await login(client)
        await client.post(
            "/api/v1/links/",
            headers=auth_header(sahip_token),
            json={"title": "Kaanin linki", "url": "https://ornek.com"},
        )

        await register_user(client, username="baskasi", email="baskasi@example.com")
        baskasi_token = await login(client, identifier="baskasi@example.com")
        await client.post(
            "/api/v1/links/",
            headers=auth_header(baskasi_token),
            json={"title": "Baskasinin linki", "url": "https://ornek2.com"},
        )

        data = (await client.get("/api/v1/p/baskasi")).json()["data"]

        assert [link["title"] for link in data["links"]] == ["Baskasinin linki"]

    async def test_public_sayfadan_click_kaydedilebilir(self, client):
        """Public sayfa, mevcut public click endpoint'i ile sayaci artirabilmeli."""
        await register_user(client)
        token = await login(client)
        await client.post(
            "/api/v1/links/",
            headers=auth_header(token),
            json={"title": "Bir", "url": "https://ornek.com"},
        )
        link = (await client.get(PROFILE_URL)).json()["data"]["links"][0]

        response = await client.post(f"/api/v1/links/{link['id']}/click")

        assert response.status_code == 200
        assert response.json()["data"]["redirect_url"] == "https://ornek.com"

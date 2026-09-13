"""Link CRUD, siralama, toggle ve analytics testleri."""
import pytest

from core.exceptions import NotFoundException
from services.link.link_service import LinkService
from tests.conftest import auth_header, login, register_user

LINK = {"title": "GitHub", "url": "https://github.com/kaandinler"}


async def create_link(client, **overrides):
    response = await client.post("/api/v1/links/", json={**LINK, **overrides})
    assert response.status_code == 201, response.text
    return response.json()["data"]


class TestCreateLink:
    async def test_link_olusturulur(self, auth_client):
        link = await create_link(auth_client)

        assert link["title"] == "GitHub"
        assert link["url"] == "https://github.com/kaandinler"
        assert link["is_active"] is True
        assert link["click_count"] == 0

    async def test_sema_olmayan_url_https_ile_tamamlanir(self, auth_client):
        link = await create_link(auth_client, url="github.com/kaandinler")
        assert link["url"] == "https://github.com/kaandinler"

    async def test_order_index_artarak_atanir(self, auth_client):
        birinci = await create_link(auth_client, title="Bir")
        ikinci = await create_link(auth_client, title="Iki")

        assert ikinci["order_index"] > birinci["order_index"]

    @pytest.mark.parametrize(
        "alan,deger",
        [
            ("url", "bu bir url degil"),
            ("title", ""),
            ("background_color", "kirmizi"),   # hex olmali
            ("border_radius", 999),            # 0-50 araligi
        ],
    )
    async def test_gecersiz_veri_422(self, auth_client, alan, deger):
        response = await auth_client.post("/api/v1/links/", json={**LINK, alan: deger})
        assert response.status_code == 422

    async def test_tokensiz_401(self, client):
        response = await client.post("/api/v1/links/", json=LINK)
        assert response.status_code == 401


class TestCreateLinkHataYonetimi:
    async def test_servis_hatasi_201_donmez(self, auth_client, monkeypatch):
        """Regresyon: create_link'teki try/except her hatayi yakalayip
        ErrorResponse donuyordu, ama endpoint'in status_code'u 201 oldugu icin
        basarisiz istekler "201 Created" ile yanitlaniyordu.
        """

        async def patlayan_create(*args, **kwargs):
            raise NotFoundException("Simule edilmis hata")

        monkeypatch.setattr(LinkService, "create_link", patlayan_create)

        response = await auth_client.post("/api/v1/links/", json=LINK)

        assert response.status_code == 404
        assert response.json()["status"] == "error"


class TestListLinks:
    async def test_kullanicinin_linkleri_sirali_doner(self, auth_client):
        await create_link(auth_client, title="Bir")
        await create_link(auth_client, title="Iki")

        response = await auth_client.get("/api/v1/links/")

        assert response.status_code == 200
        data = response.json()["data"]
        assert [link["title"] for link in data] == ["Bir", "Iki"]

    async def test_pasif_linkler_varsayilan_olarak_gizli(self, auth_client):
        link = await create_link(auth_client)
        await auth_client.patch(f"/api/v1/links/{link['id']}/toggle")

        aktif = (await auth_client.get("/api/v1/links/")).json()["data"]
        hepsi = (
            await auth_client.get("/api/v1/links/", params={"include_inactive": True})
        ).json()["data"]

        assert aktif == []
        assert len(hepsi) == 1


class TestUpdateDeleteLink:
    async def test_link_guncellenir(self, auth_client):
        link = await create_link(auth_client)

        response = await auth_client.put(
            f"/api/v1/links/{link['id']}", json={"title": "Yeni Baslik"}
        )

        assert response.status_code == 200
        assert response.json()["data"]["title"] == "Yeni Baslik"
        # Dokunulmayan alanlar korunmali
        assert response.json()["data"]["url"] == link["url"]

    async def test_link_silinir(self, auth_client):
        link = await create_link(auth_client)

        silme = await auth_client.delete(f"/api/v1/links/{link['id']}")
        assert silme.status_code == 204
        assert (await auth_client.get(f"/api/v1/links/{link['id']}")).status_code == 404

    async def test_olmayan_link_404(self, auth_client):
        response = await auth_client.get("/api/v1/links/99999")
        assert response.status_code == 404


class TestLinkYetkilendirme:
    async def test_baskasinin_linkine_erisilemez(self, client):
        await register_user(client)
        sahip_token = await login(client)
        link = (
            await client.post(
                "/api/v1/links/", json=LINK, headers=auth_header(sahip_token)
            )
        ).json()["data"]

        await register_user(client, username="baskasi", email="baskasi@example.com")
        yabanci_token = await login(client, identifier="baskasi@example.com")

        for method, path in [
            ("get", f"/api/v1/links/{link['id']}"),
            ("delete", f"/api/v1/links/{link['id']}"),
        ]:
            response = await getattr(client, method)(
                path, headers=auth_header(yabanci_token)
            )
            assert response.status_code == 403, f"{method} {path}"

    async def test_link_listeleri_kullaniciya_ozel(self, client):
        await register_user(client)
        sahip_token = await login(client)
        await client.post("/api/v1/links/", json=LINK, headers=auth_header(sahip_token))

        await register_user(client, username="baskasi", email="baskasi@example.com")
        yabanci_token = await login(client, identifier="baskasi@example.com")

        response = await client.get(
            "/api/v1/links/", headers=auth_header(yabanci_token)
        )

        assert response.json()["data"] == []


class TestReorderToggleClick:
    async def test_linkler_yeniden_siralanir(self, auth_client):
        bir = await create_link(auth_client, title="Bir")
        iki = await create_link(auth_client, title="Iki")

        response = await auth_client.post(
            "/api/v1/links/reorder", json={"link_ids": [iki["id"], bir["id"]]}
        )

        assert response.status_code == 200
        assert [link["title"] for link in response.json()["data"]] == ["Iki", "Bir"]

    async def test_eksik_id_ile_reorder_reddedilir(self, auth_client):
        bir = await create_link(auth_client, title="Bir")
        await create_link(auth_client, title="Iki")

        response = await auth_client.post(
            "/api/v1/links/reorder", json={"link_ids": [bir["id"]]}
        )

        assert response.status_code == 403

    async def test_toggle_aktiflik_durumunu_degistirir(self, auth_client):
        link = await create_link(auth_client)

        kapali = await auth_client.patch(f"/api/v1/links/{link['id']}/toggle")
        assert kapali.json()["data"]["is_active"] is False

        acik = await auth_client.patch(f"/api/v1/links/{link['id']}/toggle")
        assert acik.json()["data"]["is_active"] is True

    async def test_click_sayaci_artar_ve_public(self, client):
        """Click endpoint'i token istemez

        (public profil sayfasindan cagrilir).
        """
        await register_user(client)
        token = await login(client)
        link = (
            await client.post("/api/v1/links/", json=LINK, headers=auth_header(token))
        ).json()["data"]

        response = await client.post(f"/api/v1/links/{link['id']}/click")

        assert response.status_code == 200
        assert response.json()["data"]["redirect_url"] == link["url"]

        guncel = (
            await client.get(f"/api/v1/links/{link['id']}", headers=auth_header(token))
        ).json()["data"]
        assert guncel["click_count"] == 1


class TestAnalytics:
    async def test_analytics_ozeti(self, auth_client):
        bir = await create_link(auth_client, title="Bir")
        iki = await create_link(auth_client, title="Iki")
        await auth_client.patch(f"/api/v1/links/{iki['id']}/toggle")
        await auth_client.post(f"/api/v1/links/{bir['id']}/click")
        await auth_client.post(f"/api/v1/links/{bir['id']}/click")

        response = await auth_client.get("/api/v1/links/analytics/summary")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total_links"] == 2
        assert data["active_links"] == 1
        assert data["total_clicks"] == 2
        # En cok tiklanan basta
        assert data["links"][0]["title"] == "Bir"

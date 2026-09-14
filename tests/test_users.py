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

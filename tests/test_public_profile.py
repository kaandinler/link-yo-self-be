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

        for alan in (
            "email",
            "hashed_password",
            "id",
            "is_admin",
            "onboarding_completed",
            "profile_completed",
        ):
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


SITEMAP_URL = "/api/v1/p/sitemap/profiles"


async def _kullanici_ve_link(client, username: str, link_sayisi: int = 1) -> str:
    """Kullanici acar, giris yapar ve istenen sayida link ekler."""
    await register_user(client, username=username, email=f"{username}@example.com")
    token = await login(client, identifier=f"{username}@example.com")
    for sira in range(link_sayisi):
        response = await client.post(
            "/api/v1/links/",
            json={"title": f"Link {sira}", "url": f"https://ornek.test/{sira}"},
            headers=auth_header(token),
        )
        assert response.status_code == 201, response.text
    return token


def _adlar(response) -> list[str]:
    return [satir["username"] for satir in response.json()["data"]]


class TestSitemapProfiles:
    async def test_token_gerektirmez(self, client):
        await _kullanici_ve_link(client, "ada")

        response = await client.get(SITEMAP_URL)

        assert response.status_code == 200
        assert _adlar(response) == ["ada"]

    async def test_linki_olmayan_profil_listelenmiyor(self, client):
        # Kayit olup hicbir sey eklememis hesabin sayfasi bos; sitemap
        # arama motoruna "onemli sayfalarim" diyor, bos sayfa oraya girmemeli.
        await register_user(client, username="bos", email="bos@example.com")
        await _kullanici_ve_link(client, "dolu")

        response = await client.get(SITEMAP_URL)

        assert _adlar(response) == ["dolu"]

    async def test_pasif_link_tek_basina_yetmiyor(self, client):
        token = await _kullanici_ve_link(client, "gizli")
        linkler = (
            await client.get("/api/v1/links/", headers=auth_header(token))
        ).json()["data"]
        response = await client.patch(
            f"/api/v1/links/{linkler[0]['id']}/toggle", headers=auth_header(token)
        )
        assert response.status_code == 200, response.text

        # Link'i kapatan kullanicinin sayfasinda gosterilecek bir sey kalmadi.
        assert _adlar(await client.get(SITEMAP_URL)) == []

    async def test_silinmis_kullanici_listelenmiyor(self, client):
        token = await _kullanici_ve_link(client, "giden")
        response = await client.request(
            "DELETE",
            "/api/v1/users/me",
            headers=auth_header(token),
            json={"password": DEFAULT_USER["password"]},
        )
        assert response.status_code == 204, response.text

        assert _adlar(await client.get(SITEMAP_URL)) == []

    async def test_kullanici_adina_gore_sirali_ve_sayfalanabilir(self, client):
        for ad in ("ceren", "ali", "berk"):
            await _kullanici_ve_link(client, ad)

        hepsi = await client.get(SITEMAP_URL)
        assert _adlar(hepsi) == ["ali", "berk", "ceren"]

        # Sayfalama tutarli olmali: sabit siralama olmadan ayni kayit iki
        # sayfada birden cikabilir ya da hic cikmayabilir.
        ilk = await client.get(SITEMAP_URL, params={"limit": 2, "offset": 0})
        ikinci = await client.get(SITEMAP_URL, params={"limit": 2, "offset": 2})
        assert _adlar(ilk) == ["ali", "berk"]
        assert _adlar(ikinci) == ["ceren"]

    async def test_son_degisiklik_link_eklenince_de_ilerliyor(self, client):
        token = await _kullanici_ve_link(client, "ada")
        once = (await client.get(SITEMAP_URL)).json()["data"][0]["last_modified"]

        response = await client.post(
            "/api/v1/links/",
            json={"title": "Yeni", "url": "https://ornek.test/yeni"},
            headers=auth_header(token),
        )
        assert response.status_code == 201, response.text

        sonra = (await client.get(SITEMAP_URL)).json()["data"][0]["last_modified"]
        # Yalnizca User.updated_at'e bakilsaydi link eklemek tarihi
        # ilerletmezdi ve arama motoru degisikligi gormezdi.
        assert sonra >= once

    async def test_sitemap_adli_kullanici_ucu_golgelemiyor(self, client):
        # "/sitemap/profiles" iki segmentli oldugu icin "/{username}" ile
        # cakismiyor. Tek segmentli yazilsaydi bu kullanici erisilemezdi.
        await _kullanici_ve_link(client, "sitemap")

        profil = await client.get("/api/v1/p/sitemap")
        assert profil.status_code == 200
        assert profil.json()["data"]["username"] == "sitemap"

        assert _adlar(await client.get(SITEMAP_URL)) == ["sitemap"]

    async def test_limit_ust_sinirin_ustunde_reddediliyor(self, client):
        response = await client.get(SITEMAP_URL, params={"limit": 100000})

        assert response.status_code == 422


COUNT_URL = "/api/v1/p/sitemap/count"


class TestSitemapCount:
    """Sayim, sitemap'i parcalara bolmek icin.

    Sayim ile liste ayni kosulu kullanmak zorunda: ayrisirlarsa parca
    sayisi liste uzunluguyla tutmaz ve bu yalnizca profil sayisi belirli
    bir esige gelince ortaya cikar.
    """

    async def test_token_gerektirmez(self, client):
        await _kullanici_ve_link(client, "ada")

        response = await client.get(COUNT_URL)

        assert response.status_code == 200
        assert response.json()["data"]["count"] == 1

    async def test_bos_veritabaninda_sifir(self, client):
        response = await client.get(COUNT_URL)

        assert response.json()["data"]["count"] == 0

    async def test_cok_linkli_kullanici_bir_kez_sayiliyor(self, client):
        # Gruplamadan dogrudan count() alinsaydi bu 3 donerdi.
        await _kullanici_ve_link(client, "ada", link_sayisi=3)

        assert (await client.get(COUNT_URL)).json()["data"]["count"] == 1

    async def test_sayim_liste_uzunluguyla_ayni(self, client):
        for ad in ("ali", "berk", "ceren"):
            await _kullanici_ve_link(client, ad, link_sayisi=2)
        # Listeye girmemesi gerekenler.
        await register_user(client, username="bos", email="bos@example.com")

        sayim = (await client.get(COUNT_URL)).json()["data"]["count"]
        liste = _adlar(await client.get(SITEMAP_URL, params={"limit": 5000}))

        assert sayim == len(liste) == 3

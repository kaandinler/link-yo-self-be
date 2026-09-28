"""Sosyal hesap CRUD testleri.

Platform ve SocialAccount modelleri ilk migration'dan beri veritabaninda
duruyordu ama hicbir uc onlara dokunmuyordu; bu dosya yeni uclari
kapsiyor.

Testler platformlari kendisi ekliyor (seed_platforms): uretimdeki seed
bir migration ile geliyor, testler ise tablolari create_all ile kuruyor
ve migration calistirmiyor.
"""

import pytest

from tests.conftest import (
    DEFAULT_USER,
    auth_header,
    login,
    register_user,
    seed_platforms,
)

YOL = "/api/v1/social-accounts"


@pytest.fixture
def hesap():
    """Gecerli bir olusturma govdesi uretir (platform_id disinda)."""

    def kur(platform_id: int, **degisiklikler):
        return {
            "platform_id": platform_id,
            "username": "kaandinler",
            "profile_url": "https://github.com/kaandinler",
            **degisiklikler,
        }

    return kur


async def ikinci_kullanici(client) -> str:
    """Ikinci bir kullanici kaydedip token'ini doner (sahiplik testleri icin)."""
    await register_user(client, username="baskasi", email="baskasi@example.com")
    return await login(client, identifier="baskasi@example.com")


class TestPlatformListesi:
    async def test_platformlar_ada_gore_sirali_donuyor(self, auth_client, app):
        await seed_platforms(app, "youtube", "github", "instagram")

        yanit = await auth_client.get(f"{YOL}/platforms")

        assert yanit.status_code == 200
        adlar = [p["name"] for p in yanit.json()["data"]]
        assert adlar == ["github", "instagram", "youtube"]

    async def test_platforms_account_id_olarak_yorumlanmaz(self, auth_client, app):
        """Regresyon: /platforms rotasi /{account_id}'den once tanimli olmali.

        Sonra gelseydi FastAPI "platforms"i int account_id'ye cevirmeye
        calisir ve uc 422 dondururdu.
        """
        await seed_platforms(app, "github")

        yanit = await auth_client.get(f"{YOL}/platforms")

        assert yanit.status_code != 422

    async def test_tokensiz_401(self, client):
        assert (await client.get(f"{YOL}/platforms")).status_code == 401


class TestOlusturma:
    async def test_hesap_olusturulur(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")

        yanit = await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))

        assert yanit.status_code == 201, yanit.text
        veri = yanit.json()["data"]
        assert veri["platform_id"] == kimlikler["github"]
        assert veri["username"] == "kaandinler"
        assert veri["profile_url"] == "https://github.com/kaandinler"

    async def test_semasiz_adres_https_ile_tamamlanir(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")

        yanit = await auth_client.post(
            f"{YOL}/",
            json=hesap(kimlikler["github"], profile_url="github.com/kaandinler"),
        )

        assert yanit.json()["data"]["profile_url"] == "https://github.com/kaandinler"

    async def test_kullanici_adindaki_bosluk_kirpilir(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")

        yanit = await auth_client.post(
            f"{YOL}/", json=hesap(kimlikler["github"], username="  kaandinler  ")
        )

        assert yanit.json()["data"]["username"] == "kaandinler"

    async def test_olmayan_platform_404(self, auth_client, app, hesap):
        """FOREIGN KEY ihlali 500 olarak disari cikmamali."""
        await seed_platforms(app, "github")

        yanit = await auth_client.post(f"{YOL}/", json=hesap(9999))

        assert yanit.status_code == 404

    async def test_ayni_platform_ayni_ad_ikinci_kez_409(self, auth_client, app, hesap):
        """uq_user_platform_username ihlali 500 degil 409 olmali."""
        kimlikler = await seed_platforms(app, "github")
        govde = hesap(kimlikler["github"])
        assert (await auth_client.post(f"{YOL}/", json=govde)).status_code == 201

        yanit = await auth_client.post(f"{YOL}/", json=govde)

        assert yanit.status_code == 409

    async def test_ayni_platformda_farkli_ad_kabul_ediliyor(
        self, auth_client, app, hesap
    ):
        """Kisit uclunun birlesiminde; ayni platformda ikinci hesap serbest."""
        kimlikler = await seed_platforms(app, "github")
        await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))

        yanit = await auth_client.post(
            f"{YOL}/", json=hesap(kimlikler["github"], username="ikinci-hesap")
        )

        assert yanit.status_code == 201

    async def test_iki_kullanici_ayni_adi_kullanabilir(self, client, app, hesap):
        """Kisit kullanici basina; baskasinin kaydi engel olmamali."""
        kimlikler = await seed_platforms(app, "github")
        await register_user(client)
        ilk = auth_header(await login(client))
        assert (
            await client.post(f"{YOL}/", json=hesap(kimlikler["github"]), headers=ilk)
        ).status_code == 201

        ikinci = auth_header(await ikinci_kullanici(client))
        yanit = await client.post(
            f"{YOL}/", json=hesap(kimlikler["github"]), headers=ikinci
        )

        assert yanit.status_code == 201

    @pytest.mark.parametrize(
        "alan,deger",
        [
            ("username", ""),
            ("username", "   "),
            ("profile_url", "bu bir adres degil"),
            ("profile_url", ""),
            ("platform_id", 0),
        ],
    )
    async def test_gecersiz_alan_422(self, auth_client, app, hesap, alan, deger):
        kimlikler = await seed_platforms(app, "github")
        # Govde once kuruluyor, sonra alan degistiriliyor: platform_id'yi
        # hem konumsal hem anahtar olarak vermek cakisirdi.
        govde = hesap(kimlikler["github"])
        govde[alan] = deger

        yanit = await auth_client.post(f"{YOL}/", json=govde)

        assert yanit.status_code == 422

    async def test_tokensiz_401(self, client, app, hesap):
        kimlikler = await seed_platforms(app, "github")

        yanit = await client.post(f"{YOL}/", json=hesap(kimlikler["github"]))

        assert yanit.status_code == 401


class TestListelemeVeOkuma:
    async def test_yalnizca_kendi_hesaplari_donuyor(self, client, app, hesap):
        kimlikler = await seed_platforms(app, "github", "youtube")
        await register_user(client)
        ilk = auth_header(await login(client))
        await client.post(f"{YOL}/", json=hesap(kimlikler["github"]), headers=ilk)

        ikinci = auth_header(await ikinci_kullanici(client))
        await client.post(
            f"{YOL}/",
            json=hesap(kimlikler["youtube"], username="baskasinin-hesabi"),
            headers=ikinci,
        )

        benim = (await client.get(f"{YOL}/", headers=ilk)).json()["data"]
        assert [h["username"] for h in benim] == ["kaandinler"]

    async def test_liste_ekleme_sirasinda(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github", "youtube", "instagram")
        for platform in ("youtube", "github", "instagram"):
            await auth_client.post(
                f"{YOL}/",
                json=hesap(kimlikler[platform], username=f"ad-{platform}"),
            )

        liste = (await auth_client.get(f"{YOL}/")).json()["data"]

        assert [h["username"] for h in liste] == [
            "ad-youtube",
            "ad-github",
            "ad-instagram",
        ]

    async def test_tek_hesap_okunur(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        olusan = (
            await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))
        ).json()["data"]

        yanit = await auth_client.get(f"{YOL}/{olusan['id']}")

        assert yanit.status_code == 200
        assert yanit.json()["data"]["id"] == olusan["id"]

    async def test_olmayan_hesap_404(self, auth_client):
        assert (await auth_client.get(f"{YOL}/9999")).status_code == 404

    async def test_baskasinin_hesabi_okunamaz(self, client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        await register_user(client)
        ilk = auth_header(await login(client))
        olusan = (
            await client.post(f"{YOL}/", json=hesap(kimlikler["github"]), headers=ilk)
        ).json()["data"]

        ikinci = auth_header(await ikinci_kullanici(client))
        yanit = await client.get(f"{YOL}/{olusan['id']}", headers=ikinci)

        assert yanit.status_code == 403


class TestGuncelleme:
    async def test_kullanici_adi_guncellenir(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        olusan = (
            await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))
        ).json()["data"]

        yanit = await auth_client.put(
            f"{YOL}/{olusan['id']}", json={"username": "yeni-ad"}
        )

        assert yanit.status_code == 200
        assert yanit.json()["data"]["username"] == "yeni-ad"
        # Verilmeyen alan degismemeli.
        assert yanit.json()["data"]["profile_url"] == olusan["profile_url"]

    async def test_ayni_degerle_guncelleme_409_vermez(self, auth_client, app, hesap):
        """Kayit kendisiyle cakisiyor sayilmamali.

        Cakisma kontrolu kaydin kendisini hariç tutmasaydi, bir hesap
        hicbir alani degismeden guncellenemezdi.
        """
        kimlikler = await seed_platforms(app, "github")
        olusan = (
            await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))
        ).json()["data"]

        yanit = await auth_client.put(
            f"{YOL}/{olusan['id']}", json={"username": olusan["username"]}
        )

        assert yanit.status_code == 200

    async def test_baska_kayitla_cakisan_guncelleme_409(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))
        ikinci = (
            await auth_client.post(
                f"{YOL}/", json=hesap(kimlikler["github"], username="ikinci")
            )
        ).json()["data"]

        yanit = await auth_client.put(
            f"{YOL}/{ikinci['id']}", json={"username": "kaandinler"}
        )

        assert yanit.status_code == 409

    async def test_platform_degisimi_olmayan_id_ile_404(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        olusan = (
            await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))
        ).json()["data"]

        yanit = await auth_client.put(
            f"{YOL}/{olusan['id']}", json={"platform_id": 9999}
        )

        assert yanit.status_code == 404

    async def test_bos_govde_422(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        olusan = (
            await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))
        ).json()["data"]

        yanit = await auth_client.put(f"{YOL}/{olusan['id']}", json={})

        assert yanit.status_code == 422

    async def test_baskasinin_hesabi_guncellenemez(self, client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        await register_user(client)
        ilk = auth_header(await login(client))
        olusan = (
            await client.post(f"{YOL}/", json=hesap(kimlikler["github"]), headers=ilk)
        ).json()["data"]

        ikinci = auth_header(await ikinci_kullanici(client))
        yanit = await client.put(
            f"{YOL}/{olusan['id']}", json={"username": "ele-gecirdim"}, headers=ikinci
        )

        assert yanit.status_code == 403
        # Kayit gercekten degismemis olmali.
        kalan = (await client.get(f"{YOL}/{olusan['id']}", headers=ilk)).json()["data"]
        assert kalan["username"] == "kaandinler"


class TestSilme:
    async def test_hesap_silinir(self, auth_client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        olusan = (
            await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))
        ).json()["data"]

        yanit = await auth_client.delete(f"{YOL}/{olusan['id']}")

        assert yanit.status_code == 204
        assert (await auth_client.get(f"{YOL}/{olusan['id']}")).status_code == 404
        assert (await auth_client.get(f"{YOL}/")).json()["data"] == []

    async def test_silinen_ad_yeniden_kullanilabilir(self, auth_client, app, hesap):
        """Silme sonrasi ayni birlesim tekrar eklenebilmeli."""
        kimlikler = await seed_platforms(app, "github")
        olusan = (
            await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))
        ).json()["data"]
        await auth_client.delete(f"{YOL}/{olusan['id']}")

        yanit = await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))

        assert yanit.status_code == 201

    async def test_olmayan_hesap_404(self, auth_client):
        assert (await auth_client.delete(f"{YOL}/9999")).status_code == 404

    async def test_baskasinin_hesabi_silinemez(self, client, app, hesap):
        kimlikler = await seed_platforms(app, "github")
        await register_user(client)
        ilk = auth_header(await login(client))
        olusan = (
            await client.post(f"{YOL}/", json=hesap(kimlikler["github"]), headers=ilk)
        ).json()["data"]

        ikinci = auth_header(await ikinci_kullanici(client))
        yanit = await client.delete(f"{YOL}/{olusan['id']}", headers=ikinci)

        assert yanit.status_code == 403
        assert (
            await client.get(f"{YOL}/{olusan['id']}", headers=ilk)
        ).status_code == 200


class TestHesapKapatma:
    async def test_kapali_hesabin_sosyal_hesaplarina_erisilemiyor(
        self, auth_client, app, hesap
    ):
        """Hesap kapaninca token gecersizlesiyor; bu uclar da erisilemez.

        Ayni kontrol diger uclarda var; yeni bir router eklerken
        atlanmadigini burada da olcuyoruz.
        """
        kimlikler = await seed_platforms(app, "github")
        await auth_client.post(f"{YOL}/", json=hesap(kimlikler["github"]))

        kapat = await auth_client.request(
            "DELETE", "/api/v1/users/me", json={"password": DEFAULT_USER["password"]}
        )
        assert kapat.status_code == 204

        assert (await auth_client.get(f"{YOL}/")).status_code == 401
